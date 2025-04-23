import socket
import threading
import json
import time
import random
from collections import defaultdict

HOST = '0.0.0.0'
PORT = 20250

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