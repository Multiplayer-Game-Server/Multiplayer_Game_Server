import socket
import threading
import json
import time
import random
from collections import defaultdict

HOST = '0.0.0.0'
PORT = 20250

#лучше создать класс игрока, но тогда надо совсем немного 
# поменять пару строк в функциях 
class Player:
    def __init__(self, client_socket, client_addr):
        self.socket = client_socket  # player's socket for communication
        self.address = client_addr  # player's IP and port
        self.answered = False  # Whether the player has answered the current question
        self.score = 0  

class Game:
    def __init__(self, game_id, player_socket):
        self.players_sockets = [player_socket]
        self._running = False
        self._thread = None
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

    def start(self):
        """ Run a thread """
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
    
    def _run(self):
        pass

    def get_questions(self):
        pass # will be implemented when the database will be
    
    def handlePlayerConnect(self, player):
        """Add a player to the game"""
        with self.lock:
            self.players.append(player)
            print(f"Player {player[1][0]}:{player[1][1]} joined game {self.id}.")
    
    def handle_ready(self, player):
        """Mark a player as ready and start the game if all players are ready"""
        with self.lock:
            print(f"Player {player[1][0]}:{player[1][1]} is ready.")
            self.ready_players += 1
            if self.ready_players == len(self.players):
                print(f"All players are ready. Starting game {self.id}.")
                #self.broadcast(json.dumps({"type": "info", "message": "All players are ready. Starting the game!"}))
                self.start_game()
    
    def start_game(self):
        """Start the game"""
        with self.lock:
            self.game_state = 'playing'
            print(f"Game {self.id} is starting!")
            self.next_round()
    
    def next_round(self):
        """Move to the next round"""
        with self.lock:
            if self.current_round >= self.number_of_rounds:
                self.end_game()
                return
            
            self.current_round += 1
            #загрузить сначала 5 рандомных вопросов и выводить их  в раундах
            self.current_question = random.choice(self.questions) #will change when the database will be
            self.answers_received = 0
            self.question_start_time = time.time()
            
            # Reset the answered flag for all players
            for player in self.players:
                player.answered = False
                
            print(f"Starting round {self.current_round} in game {self.id}.")
            self.broadcast_question()
    
    def broadcast_question(self): 
        """Send the current question to all players"""
        question_data = {
            'type': 'question',
            'round': self.current_round,
            'question': self.current_question['question'],
            'options': self.current_question['options']
        }
        self.broadcast(json.dumps(question_data))

    def process_answer(self, player, round_number, answer_index):
        """Process a player's answer"""
        with self.lock:
            if self.game_state != 'playing' or self.current_question is None:
                return
            
            # Ensure the answer is for the current round
            if round_number != self.current_round:
                return
            
            # Ensure a player can only answer once per round
            if hasattr(player, 'answered') and player.answered:
                return
            player.answered = True  # Mark the player as having answered
            
            self.answers_received += 1
            
            # Check if the answer is correct
            correct = answer_index == self.current_question['answer']
            if correct:
                self.scores[player] += 1  # Award points for a correct answer
            
            response = {
                'type': 'correct answer',
                'correct_answ': chr(65 + self.current_question['answer']),  # Convert index to letter (A, B, C, D)
                'your_res': correct,
                'curr_score': [self.scores[p] for p in self.players]
            }
            
            # Send the response to the player
            player[0].send(json.dumps(response).encode())
            
            # Check if all players have answered
            if self.answers_received >= len(self.players):
                self.handle_all_answered()
        
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
            print(f"Game {self.id} is ending.")
            self.game_state = 'finished'

            # Determine the winner
            winner = None
            if self.scores:
                winner = max(self.scores, key=self.scores.get)  # Player with the highest score

            #  results
            results = {
                'type': 'end game',
                'winner': f"{winner[1][0]}:{winner[1][1]}" if winner else "No winner",
                'curr_score': [self.scores[player] for player in self.players]
            }

            # Broadcast the results to all players
            self.broadcast(json.dumps(results))

            # Close all player connections
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
        self.games = {}
        self.next_game_id = 0
        self.buffer_size = 10000
        self.lock = threading.Lock()

    def createGame(self, player):
        ''' 
        The function is responsible for the creation of the game. 
        It returns game id (integer) 
        '''
        game_id = self.next_game_id
        self.next_game_id += 1
        game = Game(game_id, player)
        with self.lock:
            self.games[game_id] = game
        game.start()
        return game_id, 999

    def connectGame(self, game_id, player):
        ''' 
        The function is responsible for connecting the player to the game. 
        It returns true if the connection was successful, otherwise false 
        '''
        game = self.games[game_id]
        if (not game):
            return (None, -1, [])
        player_id, list_players = game.handlePlayerConnect(player)
        return (game_id, player_id, list_players)

    def getMessage(self, client_socket):
        '''
        The function receives the full json message of the player and 
        returns it as a python dictionary.
        '''
        data = client_socket.recv(self.buffer_size)
        return json.loads(data.decode())

    def manage_new_connection(self):
        '''
        Starts a main loop in which it handles the connection of new players.
        '''
        while True:
            # Pending connection of a new player  
            client_socket, client_addr = self.server_socket.accept()
            client_thread = threading.Thread(
                target=self.handle_client,
                args=(client_socket, client_addr),
                daemon=True
            )
            client_thread.start()
            print(f"Started thread for {client_addr}")
        
    def handle_client(self, client_socket, client_addr):
        player = client_socket, client_addr
        print(f"New connection from {client_addr[0]}: {client_addr[1]}")

        # Waiting for a request from the newly connected player
        message = self.getMessage(client_socket)
        print(f"Got message from {client_addr[0]}: {client_addr[1]}:")
        print("-"*30, f"\n{message}\n", "-"*30)

        # Create a room and generate a reply to the player if there was a request to create a room 
        if (message['type'] == 'create'): 
            game_id, player_id = self.createGame(player)
            answer = json.dumps({
                "type": "status",
                "player_id": player_id,
                "game_id": game_id,
                "list_of_players": [player_id]
            })
        # Connects the player to the room and generate a reply to the player.
        # Cоединяет игрока с комнатой и формируем ответ игроку.
        elif (message['type'] == 'connect'):
            game_id = message['game_id']
            game_id, player_id, list_players = self.connectGame(game_id, player)
            answer = json.dumps({
                "type": "status",
                "player_id": player_id,
                "game_id": game_id,
                "list_of_players": list_players
            })
         
         
        #либо вынести обработку ответа и готов к игре в дргугую функцию
         #Handle if clinet ready to start the game   
        elif message['type'] == 'ready to start':
            game_id = message['game_id']
            game = self.games[game_id]
            game.handle_ready(player)
            answer = json.dumps({"type": "ready_acknowledged"})
            
        # Handle if client  answer the question
        elif message['type'] == 'answer':
            game_id = message['game_id']
            game = self.games[game_id]
            game.process_answer(player, message['round'], message['answer'])
            
        else:
            answer = {"type": "Error"}
    
        # Send response
        client_socket.send(answer.encode())

    def serve(self, host, port, max_num_player):
        '''
        The function creates a socket, configures it, and starts listening for connections 
        '''
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(max_num_player)
        print(self.server_socket)
        self.manage_new_connection()

if (__name__ == '__main__'):
    server = Server()
    server.serve(HOST, PORT, 10)