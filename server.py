import socket
import threading
import json
import time
import random
from enum import Enum
from collections import defaultdict

HOST = '0.0.0.0'
PORT = 20250

'''обсудить использование enum, а не текстовых определений'''
class GameStates(Enum):
    PLAYING = 0
    WAITING = 1
    FINISHED = 2

class MessageType(Enum):
    QUESTION = 0
    ANSWER_RESULTS = 1
    GAME_RESULT = 2

class Game:
    def __init__(self, game_id):
        self.id = game_id
        self.players = []
        self.game_state = 'waiting'  # waiting, playing, finished
        self.current_question = None
        self.current_round = 0
        self.answers_received = 0
        self.question_start_time = 0
        self.scores = defaultdict(int) # player_id -> score
        self.questions = self.get_questions()
        self.lock = threading.Lock()
        self.number_of_rounds = 5
        self.delay_between_questions = 2 # Seconds
    
    
    def get_questions(self):
        pass #will be implemented when the database will be
    
    def handlePlayerConnect(self, player): #add player to the game
        with self.lock:
            self.players.append(player)
            # if len(self.players) >= 2 and self.game_state == 'waiting':
            #     self.start_game()
    
    def start_game(self):
        with self.lock:
            self.game_state = 'playing'
            self.next_round()
    
    def next_round(self):
        with self.lock:
            self.current_round += 1
            self.current_question = random.choice(self.questions)
            self.answers_received = 0
            self.question_start_time = time.time()
            
            # Reset the answered flag for all players
            for player in self.players:
                player.answered = False
            
            self.broadcast_question()
    
    def broadcast_question(self): #send the current question to all players
        question_data = {
            'type': 'question',
            'round': self.current_round,
            'question': self.current_question['question'],
            'options': self.current_question['options']
        }
        self.broadcast(json.dumps(question_data))
    
    def process_answer(self, player, answer_index):
        with self.lock:
            if self.game_state != 'playing' or self.current_question is None:
                return False
            
            # Ensure a player can only answer once per round
            if hasattr(player, 'answered') and player.answered:
                return False
            player.answered = True  # Mark the player as having answered
            
            self.answers_received += 1
            #response_time = time.time() - self.question_start_time
            
            if answer_index == self.current_question['answer']:
                points = 10
                self.scores[player] += points
                response = {
                    'type': 'answer_result',
                    'correct': True,
                    'points': points,
                    'total_score': self.scores[player]
                }
            else:
                response = {
                    'type': 'answer_result',
                    'correct': False,
                    'correct_answer': self.current_question['answer'],
                    'total_score': self.scores[player]
                }
            
            player.conn.send(json.dumps(response).encode())
            
            if self.answers_received >= len(self.players):
                self.handle_all_answered()
            
            return True
        
    def handle_all_answered(self):
        """Handle when all players have answered"""
        if self.current_round >= self.number_of_rounds:
            self.end_game()
        else:
            score_table = self.get_result()
            self.broadcast(json.dumps(score_table))
            time.sleep(self.delay_between_questions)
            self.next_round()

    def get_result(self):
        results = {
            'type': 'game_results',
            'scores': {p.id: self.scores[p] for p in self.players}
        }
        return results

    def end_game(self):
        """End the game and announce results"""
        with self.lock:
            print("Stop game and send results")
            self.game_state = 'finished'
            results = self.get_result()
            self.broadcast(json.dumps(results))
            self.close_connection_players(self.players)
    
    def close_connection_players(self, players):
        for player in players:
            print(f"Close connection: {player[1][0]}: {player[1][1]}")
            player[0].close()

    def broadcast(self, message):
        """Send a message to all players"""
        for player in self.players:
            try:
                print(f"Send message to {player[1][0]}: {player[1][1]}")
                player.conn.send(message.encode())
            except:
                print(f"Can't send message to {player[1][0]}: {player[1][1]}")
                self.handle_disconnect(player)
    
    def handle_disconnect(self, player):
        """Handle a player disconnecting"""
        """Надо будет рассмотреть этот метод позже"""
        with self.lock:
            if player in self.players:
                print(f"Close connection: {player[1][0]}: {player[1][1]}")
                self.players.remove(player)
                player[0].close()
                if self.game_state == 'playing':
                    if len(self.players) < 1:
                        self.end_game()
    
    

class Server:
    def __init__(self):
        self.games = []
        self.next_game_id = 0
        self.buffer_size = 4096

    def handleCreateGame(self):
        game_id = self.next_game_id
        self.games.append(Game(game_id))
        self.next_game_id += 1

    def handleConnectGame(self, game_id, player):
        game = self.games[game_id]
        game.handlePlayerConnect(player)

    def manageMessageFromClient(self, client_socket):
        message = b""
        while True:
            data = client_socket.recv(self.buffer_size)
            if (not data):
                break
            message += data
        return message.decode()

    def manageNewConnection(self):
        client_socket, client_addr = self.server_socket.accept()
        print(f"New connection from {client_addr[0]}: {client_addr[1]}")
        message = self.manageMessageFromClient(client_socket)
        print(f"Got message from {client_addr[0]}: {client_addr[1]}")
        client_socket.send(message.encode())
        print("-"*30)
        print(message)
        print("-"*30)
        client_socket.close() 

    def serve(self, host, port, max_num_player):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(max_num_player)
        print(self.server_socket)
        self.manageNewConnection()

if (__name__ == '__main__'):
    server = Server()
    server.serve(HOST, PORT, 10)