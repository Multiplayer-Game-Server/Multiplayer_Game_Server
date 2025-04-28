import socket
import threading
import json
import time
import random
from collections import defaultdict
from typing import List
from typing import Dict

HOST = '0.0.0.0'
PORT = 20250


class Player:
    def __init__(self, client_socket, client_addr, player_id):
        self.socket: socket.socket = client_socket  # player's socket for communication
        self.address = client_addr  # player's IP and port
        self.id = player_id # player's uID
        self.answered = False  # whether the player has answered the current question
        self.score = 0  # player's score

class Game:
    def __init__(self, game_id, player: Player, server):
        self.server: Server = server # reference to the server instance
        self._running = True # indicates whether the game is running at the thread and timer levels
        self._thread = None # Thread for the game
        self.deleted_players = {} # Dictionary to store disconnected players and their scores
        self.id = game_id  # Unique game ID
        self.players: List[Player] = [player] # List of players in the game
        self.game_state = 'waiting'  # states of game: waiting, playing, finished
        self.current_question = None # Current question being asked
        self.current_question_index = 0 # Index of the current question
        self.current_round = 0 # Current round number
        self.ready_players = 0  # Number of players ready to start the game
        self.answers_received = 0 # Number of players who have answered the current question
        self.question_start_time = 0 # Time when the current question was asked
        self.scores = defaultdict(int) # player_id -> score
        self.questions = self.get_questions()
        self.lock = threading.RLock() # Lock for thread safety
        self.number_of_rounds = 5 # Number of rounds in the game
        self.delay_between_questions = 3 # Delay between questions
        self.round_time_limit = 40  # Time limit for each question in seconds

    
    # function to load questions from a json file and randomly selects 5 questions
    def get_questions(self, num_questions=5):
        try:
            with open('questions.json', 'r', encoding='utf-8') as f:
                all_questions = json.load(f)
                return random.sample(all_questions, k=num_questions)
        except Exception as e:
            print(f"Error loading questions from file: {e}")
            return []

    # function for adding a player to the game
    def handlePlayerConnect(self, player: Player):
        with self.lock:
            self.players.append(player)
            print(f"Player {player.address[0]}:{player.address[1]} joined game {self.id}.")

            # notify all players about the new player
            new_player_message = {
                "type": "new player",
                "player_id": player.id
            }
            for p in self.players:
                if p != player:  
                    try:
                        p.socket.send(json.dumps(new_player_message).encode())
                    except Exception as e:
                        print(f"Error sending 'new player' message to {p.address}: {e}")
                        self.handle_disconnect(p)

            return player.id, [p.id for p in self.players]
    
    # function to check if the player is already in the game
    def handle_ready(self, player: Player):
        with self.lock:
            print(f"Player {player.address[0]}:{player.address[1]} is ready.")
            self.ready_players += 1
            print(f"Ready players: {self.ready_players}/{len(self.players)}")  

            # check if all players are ready
            if self.ready_players == len(self.players):
                print(f"All players are ready.")
                self.start_game()
    
    # starts the game 
    def start_game(self):
        print(f"Starting game {self.id}...")
        with self.lock:
            try:
                self.game_state = 'playing'
                self.next_round()
            except Exception as e:
                print(f"Error in start_game: {e}")
    
    # function for starting the next round
    def next_round(self):
        with self.lock:
            if not self._running:
                return
            # check if there are players in the game
            if len(self.players) == 0:
                print(f"No players left in game {self.id}. Ending game.")
                self.end_game()
                return
            
            # check if the game is finished
            if self.current_round >= self.number_of_rounds:
                self.end_game()
                return
            
            # choose question for the current round from the list of questions
            if self.current_question_index < len(self.questions):
                self.current_question = self.questions[self.current_question_index]
                self.current_question_index += 1  # increment the question index for the next round
            else:
                print("No more questions available.")
                self.end_game()
                return
            
            # check how many answer s have been received
            self.answers_received = 0
            # set the start time for the question
            self.question_start_time = time.time()
            
            # Reset the answered flag for all players
            for player in self.players:
                player.answered = False
                
            print(f"Starting round {self.current_round} in game {self.id}.")
            self.broadcast_question()
            
            # start the timer for the current round
            self.round_timer = threading.Timer(self.round_time_limit, self.check_time_up)
            self.round_timer.start()
            self.current_round += 1
    
    
    # check if the time is up for the current round       
    def check_time_up(self):
        with self.lock:
            if not self._running:
                return
            # Check if the game is still running and if the round time limit has been reached
            elapsed_time = time.time() - self.question_start_time
            if elapsed_time >= self.round_time_limit and self.answers_received < len(self.players):
                print(f"Time is up for round {self.current_round} in game {self.id}.")
                self.handle_all_answered()
    
    # function for broadcasting the question to all players
    def broadcast_question(self): 
        question_data = {
            'type': 'question',
            'round': self.current_round,
            'question': self.current_question['question'],
            'options': self.current_question['options']
        }
        self.broadcast(json.dumps(question_data))


    # function for processing the player's answer
    def process_answer(self, player: Player, round_number, answer_index):
        with self.lock:
             # Check if time has expired
            elapsed_time = time.time() - self.question_start_time 
            if elapsed_time >= self.round_time_limit:
                print(f"Time is up for round {self.current_round} in game {self.id}.")
                self.handle_all_answered()
                return
            
            # Ensure a player can only answer once per round
            if player.answered:
                return
            player.answered = True  # Mark the player as having answered
            
            self.answers_received += 1
            print(f"Player {player.id} answered. Total answers received: {self.answers_received}/{len(self.players)}")
            # Check if the answer is correct
            correct = answer_index == self.current_question['answer']
            if correct:
                self.scores[player] += 1  # add points to player for a correct answer
            
            # Check if all players have answered
            active_players = [p for p in self.players if p.socket]
            if self.answers_received >= len(active_players):
                self.handle_all_answered()
    
    # function for handling when all players have answered 
    def handle_all_answered(self):
        with self.lock:
            # stop the round timer if it is still running
            if hasattr(self, 'round_timer') and self.round_timer.is_alive():
                self.round_timer.cancel()
            
            print(f"All players have answered for round {self.current_round} in game {self.id}.")
            
            response = {
                'type': 'correct answer',
                'correct_answ': self.current_question['answer'] + 1, 
                'curr_score': [self.scores[p] for p in self.players],  
                'deleted_players': [{'id': player_id, 'score': score} for player_id, score in self.deleted_players.items()] 
            }
            
            self.broadcast(json.dumps(response))
            
            # transition to the next round or end the game
            if self.current_round >= self.number_of_rounds:
                self.end_game()
            else:
                time.sleep(self.delay_between_questions)
                print("Next round starting...")
                self.next_round()
                
    def get_result(self):
        """  The function returns a json response with the list of player's records  """
        results = {
            'type': 'game_results',
            'scores': {p.id: self.scores[p] for p in self.players}
        }
        return results

    def end_game(self):
        """ The function finishes the game and sends a json response to everyone about the game completion """
        with self.lock:
            # Set the game to finish game state 
            if not self._running:
                return
            self._running = False 
            print(f"Game {self.id} is ending.")
            self.game_state = 'finished'

            # If the game was completed earlier, disable the timer 
            if hasattr(self, 'round_timer') and self.round_timer.is_alive():
                self.round_timer.cancel()

            # Determine the winner (player with the highest score)
            winner = None
            if self.scores:
                winner = max(self.scores, key=self.scores.get)

            # Generate json response about game finish
            winner_player = next((p for p in self.players if p.id == winner), None)
            results = {
                'type': 'end game',
                'winner': f"{winner_player.address[0]}:{winner_player.address[1]}" if winner_player else "No winner",
                'curr_score': [self.scores[player] for player in self.players]
            }

            # Broadcast the results to all players
            self.broadcast(json.dumps(results))
            
            # Close all player connections
            self.close_connection_players(self.players)
            
            # Remove the game from the list of active games
            self.server.remove_game(self.id)
    
 
    def close_connection_players(self, players: List[Player]):
        """ The function completes the connection to all players that are passed as an argument """
        for player in players:
            if player.socket:  
                print(f"Close connection: {player.address[0]}: {player.address[1]}")
                try:
                    player.socket.close()
                    player.socket = None 
                except Exception as e:
                    print(f"Error closing socket for player {player.id}: {e}")
            else:
                print(f"Socket for player {player.id} is already closed.")

    def broadcast(self, message):
        """ The function sends a message to all players """ 
        if not isinstance(message, str):    # Convert dict to JSON string if needed
            message = json.dumps(message)

        for player in self.players:
            try:
                if player.socket:  
                    player.socket.send(message.encode()) 
                    print(f"Send message to {player.address[0]}: {player.address[1]}")
            except (ConnectionResetError, BrokenPipeError, OSError):
                print(f"Player {player.address[0]}:{player.address[1]} disconnected during broadcast.")
                self.handle_disconnect(player)
            except Exception as e:
                print(f"Error sending message to {player.address[0]}:{player.address[1]}: {e}")
                self.handle_disconnect(player)
    
    def handle_disconnect(self, player: Player):
        """ Function correctly handles player disconnection """
        with self.lock:
            if not player.socket: 
                return
            
            if player in self.players:
                print(f"Close connection: {player.address[0]}:{player.address[1]}")
                self.deleted_players[player.id] = self.scores[player]
                self.players.remove(player)
                try:
                    # Close connections to the player
                    player.socket.close()
                    player.socket = None 
                except Exception as e:
                    print(f"Error closing socket for player {player.id}: {e}")
                
                # Check if there are still players in the room, 
                # If not, finish the game
                if self.game_state == 'playing' and len(self.players) == 0:
                    self.end_game()
                else:
                    # If a player is disconnected during a round, check if the round should be ended
                    active_players = [p for p in self.players if p.socket]
                    if self.answers_received >= len(active_players):
                        self.handle_all_answered()
    
''' The main class that creates and manages games and manages player connectivity to games ''' 
class Server:
    def __init__(self):
        self.games: Dict[int, Game] = {} # List of all the games that have been created
        self.next_game_id = 0 # id for a new game instance 
        self.next_player_id = 0 # id for a new player instance 
        self.buffer_size = 10000 # buffer size for work with sockets
        self.lock = threading.Lock() # mutex for thread-safe access to shared data

    def createGame(self, player: Player) -> tuple[int, int]:
        ''' The function is responsible for the creation of the game instance. '''
        game_id = self.next_game_id 
        self.next_game_id += 1
        game = Game(game_id, player, self)
        with self.lock:
            self.games[game_id] = game
        # Return a unique id for the game and a unique in-game id for the player who created the game
        return game_id, player.id 

    def connectGame(self, game_id: int, player: Player) -> tuple[int, int, list]:
        ''' The function is responsible for connecting the player to the game '''
        game = self.games[game_id]
        if game is None:                
            return (None, -1, [])      
        player_id, list_players = game.handlePlayerConnect(player)
        return (game_id, player_id, list_players)

    def getMessage(self, client_socket: socket.socket) -> dict:
        ''' The function receives the full json message of the player '''
        data = client_socket.recv(self.buffer_size)
        return json.loads(data.decode())

    def manage_new_connection(self):
        ''' Starts a main loop in which it handles the connection of new players '''
        while True:
            # Pending connection of a new player  
            client_socket, client_addr = self.server_socket.accept()
            # Start a thread to process a new connection 
            client_thread = threading.Thread(
                target=self.handle_client,
                args=(client_socket, client_addr),
                daemon=True
            )
            client_thread.start()
            print(f"Started thread for {client_addr}")
        
    def handle_client(self, client_socket: socket.socket, client_addr):
        ''' The function handles requests from the client to create a game or connect to a game '''
        with self.lock:
            player_id = self.next_player_id
            self.next_player_id += 1
        player = Player(client_socket, client_addr, player_id)
        print(f"New connection from {client_addr[0]}: {client_addr[1]}")

        # Loop to handle multiple requests from a client
        while True:
            try:
                # Waiting for a message from the client 
                message = self.getMessage(client_socket)
                print(f"Got message from {client_addr[0]}: {client_addr[1]}: {message}")

                # If there was a request to create a new game, 
                # create the game and send the response to the client 
                if message['type'] == 'create':
                    game_id, player_id = self.createGame(player)
                    answer = {
                        "type": "status",
                        "player_id": player_id,
                        "game_id": game_id,
                        "list_of_players": [player_id]
                    }
                    client_socket.send(json.dumps(answer).encode())
                    break
                # If there was a request to connect to the game, 
                # try to connect the player to the game and send the corresponding response 
                elif message['type'] == 'connect':
                    game_id = int(message['game_id'])
                    # if room does not exist or is not in waiting state, send an error message
                    if (game_id not in self.games) or (self.games[game_id].game_state != "waiting"):
                        error_message = {
                            "type": "status",
                            "player_id": player_id,
                            "game_id": None, 
                            "list_of_players": []
                        }
                        client_socket.send(json.dumps(error_message).encode())
                        print(f"Player {client_addr[0]}:{client_addr[1]} tried to connect to a non-existent game {game_id}.")
                        continue # if connection to the game fails, continue the cycle so that the client can try again

                    # if the game exists, connect the player to the game
                    game_id, player_id, list_players = self.connectGame(game_id, player)
                    answer = {
                        "type": "status",
                        "player_id": player_id,
                        "game_id": game_id,
                        "list_of_players": list_players
                    }
                    client_socket.send(json.dumps(answer).encode())
                    break  
                # If the message is of unknown type
                else:
                    print("Error") 

            except json.JSONDecodeError:
                print(f"Invalid JSON message from {client_addr[0]}:{client_addr[1]}. Closing connection.")
                break
            except Exception as e:
                print(f"Error handling client {client_addr[0]}:{client_addr[1]}: {e}")
                break

        # Create a separate thread to listen to messages from the player 
        player_thread = threading.Thread(
            target=self.listen_to_player,
            args=(player, game_id),
            daemon=True
        )
        player_thread.start()
            
        
    # function for listening to messages from the player and processing them
    def listen_to_player(self, player: Player, game_id):
        game = self.games[game_id]
        if not game:
            print(f"Game {game_id} not found for player {player.id}")
            return
        while True:
            try:
                # Check if the player is still connected and the game is running
                if not player.socket or not game._running: 
                    break
                # Wait for a message from the player
                message = self.getMessage(player.socket)
                print(f"Got message from {player.address[0]}:{player.address[1]}: {message}")

                # handle different message types
                if message['type'] == 'ready to start':
                    game.handle_ready(player)
                    
                elif message['type'] == 'answer':
                    print("Get answer")
                    game.process_answer(player, message['round'], message['answer'])
                else:
                    print(f"Unknown message type: {message['type']}")
                    
            except (ConnectionResetError, BrokenPipeError, OSError):
                print(f"Player {player.address[0]}:{player.address[1]} disconnected.")
                game.handle_disconnect(player)
                break
            except Exception as e:
                print(f"Seems that player disconnected {player.address[0]}:{player.address[1]}: {e}")
                game.handle_disconnect(player)
                break
    
    # function for removing the game from the list of active games     
    def remove_game(self, game_id: int):
        with self.lock:
            if game_id in self.games:
                print(f"Removing game {game_id}")
                del self.games[game_id]
                
    # function creates a socket, configures it, and starts listening for connections
    def serve(self, host, port, max_num_player):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(max_num_player)
        print(f"Server is listening on {host}:{port} ")
        self.manage_new_connection()

if (__name__ == '__main__'):
    server = Server() 
    server.serve(HOST, PORT, 25) 
