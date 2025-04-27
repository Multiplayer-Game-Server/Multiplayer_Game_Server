import socket
import threading
import json
import time
from collections import defaultdict
from typing import List
from typing import Dict

HOST = '0.0.0.0'
PORT = 20250


# игра начинается сразу если подключенные игрко нажал что готов а другой не подсоединился
# проблема если клиент не отвечает
# ошибки у одного их игроково и на стороне сервера
class Player:
    def __init__(self, client_socket, client_addr, player_id):
        self.socket: socket.socket = client_socket  # player's socket for communication
        self.address = client_addr  # player's IP and port
        self.id = player_id
        self.answered = False  # Whether the player has answered the current question
        self.score = 0  # Player's score

class Game:
    def __init__(self, game_id, player: Player, server):
        self.server: Server = server
        self._running = True
        self._thread = None
        self.id = game_id
        self.players: List[Player] = [player]
        self.game_state = 'waiting'  # waiting, playing, finished
        self.current_question = None
        self.current_question_index = 0 
        self.current_round = 0
        self.ready_players = 0  # Number of players ready to start the game
        self.answers_received = 0
        self.question_start_time = 0
        self.scores = defaultdict(int) # player_id -> score
        self.questions = self.get_questions()
        self.lock = threading.RLock()
        self.number_of_rounds = 2
        self.delay_between_questions = 3 # Seconds
        self.round_time_limit = 40

  

    def get_questions(self):
        """Return a list of sample questions for testing"""
        return [
            {
                "question": "What is the capital of France?",
                "options": ["Berlin", "Madrid", "Paris", "Rome"],
                "answer": 2  # Index of the correct answer (C. Paris)
            },
            {
                "question": "Which planet is known as the Red Planet?",
                "options": ["Earth", "Mars", "Jupiter", "Venus"],
                "answer": 1  # Index of the correct answer (B. Mars)
            },
            {
                "question": "What is the largest ocean on Earth?",
                "options": ["Atlantic Ocean", "Indian Ocean", "Arctic Ocean", "Pacific Ocean"],
                "answer": 3  # Index of the correct answer (D. Pacific Ocean)
            },
            {
                "question": "Who wrote 'Romeo and Juliet'?",
                "options": ["Charles Dickens", "William Shakespeare", "Mark Twain", "D. Jane Austen"],
                "answer": 1  # Index of the correct answer (B. William Shakespeare)
            },
            {
                "question": "What is the chemical symbol for water?",
                "options": ["H2O", "CO2", "O2", "NaCl"],
                "answer": 0  # Index of the correct answer (A. H2O)
            }
        ]
    
    def handlePlayerConnect(self, player: Player):
        """Add a player to the game"""
        with self.lock:
            self.players.append(player)
            print(f"Player {player.address[0]}:{player.address[1]} joined game {self.id}.")

            # Отправить сообщение "new player" всем игрокам, кроме нового
            new_player_message = {
                "type": "new player",
                "player_id": player.id
            }
            for p in self.players:
                if p != player:  # Исключаем нового игрока
                    try:
                        p.socket.send(json.dumps(new_player_message).encode())
                    except Exception as e:
                        print(f"Error sending 'new player' message to {p.address}: {e}")
                        self.handle_disconnect(p)

            # Отправить сообщение "status" только новому игроку
            status_message = {
                "type": "status",
                "player_id": player.id,
                "game_id": self.id,
                "list_of_players": [p.id for p in self.players]
            }
            try:
                player.socket.send(json.dumps(status_message).encode())
            except Exception as e:
                print(f"Error sending 'status' message to {player.address}: {e}")
                self.handle_disconnect(player)

            # Возвращаем ID нового игрока и список всех игроков
            return player.id, [p.id for p in self.players]
    
    def handle_ready(self, player: Player):
        """Mark a player as ready and start the game if all players are ready"""
        with self.lock:
            print(f"Player {player.address[0]}:{player.address[1]} is ready.")
            self.ready_players += 1
            print(f"Ready players: {self.ready_players}/{len(self.players)}")  # Отладочный вывод

            # Проверяем, готовы ли все игроки
            if self.ready_players == len(self.players):
                print(f"All players are ready. Starting game {self.id}.")
                # Запускаем игру
                self.start_game()
    
    def start_game(self):
        print(f"Starting game {self.id}...")
        with self.lock:
            print("Lock acquired.")
            try:
                self.game_state = 'playing'
                print(f"Game {self.id} is starting!")  # Отладочный вывод
                self.next_round()
            except Exception as e:
                print(f"Error in start_game: {e}")
    
    def next_round(self):
        """Move to the next round"""
        with self.lock:
            if self.current_round >= self.number_of_rounds:
                self.end_game()
                return
            
            
            # Выбираем вопрос по индексу
            if self.current_question_index < len(self.questions):
                self.current_question = self.questions[self.current_question_index]
                self.current_question_index += 1  # Увеличиваем индекс для следующего раунда
            else:
                print("No more questions available.")
                self.end_game()
                return
            
            self.answers_received = 0
            self.question_start_time = time.time()
            
            # Reset the answered flag for all players
            for player in self.players:
                player.answered = False
                
            print(f"Starting round {self.current_round} in game {self.id}.")
            self.broadcast_question()
            
            # Установить таймер для проверки истечения времени
            self.round_timer = threading.Timer(self.round_time_limit, self.check_time_up)
            self.round_timer.start()
            
            self.current_round += 1
            
    def check_time_up(self):
        """Check if time is up for the current round"""
        with self.lock:
            elapsed_time = time.time() - self.question_start_time
            if elapsed_time >= self.round_time_limit and self.answers_received < len(self.players):
                print(f"Time is up for round {self.current_round} in game {self.id}.")
                self.handle_all_answered()
    
    def broadcast_question(self): 
        """Send the current question to all players"""
        question_data = {
            'type': 'question',
            'round': self.current_round,
            'question': self.current_question['question'],
            'options': self.current_question['options']
        }
        self.broadcast(json.dumps(question_data))

    def process_answer(self, player: Player, round_number, answer_index):
        """Process a player's answer"""
        with self.lock:
            
            # if self.game_state != 'playing' or self.current_question is None:
            #     return
            
            # # Ensure the answer is for the current round
            # if round_number != self.current_round:
            #     return
            
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
                self.scores[player] += 1  # Award points for a correct answer
            
            
            # Check if all players have answered
            if self.answers_received >= len(self.players):
                self.handle_all_answered()
        
    def handle_all_answered(self):
        """Handle when all players have answered or time is up"""
        with self.lock:
            # Остановить таймер, если он ещё работает
            if hasattr(self, 'round_timer') and self.round_timer.is_alive():
                self.round_timer.cancel()
            
            print(f"All players have answered for round {self.current_round} in game {self.id}.")
            
            # Формируем общий ответ для всех игроков
            response = {
                'type': 'correct answer',
                'correct_answ': chr(65 + self.current_question['answer']),  # Преобразуем индекс в букву (A, B, C, D)
                'curr_score': [self.scores[p] for p in self.players]  # Список очков всех игроков
            }
            
            # Отправляем ответ всем игрокам
            self.broadcast(json.dumps(response))
            
            # Переход к следующему раунду или завершение игры
            if self.current_round >= self.number_of_rounds:
                self.end_game()
            else:
                time.sleep(self.delay_between_questions)
                print("Next round starting...")
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
            self._running = False 
            print(f"Game {self.id} is ending.")
            self.game_state = 'finished'

            # Determine the winner
            winner = None
            if self.scores:
                winner = max(self.scores, key=self.scores.get)  # Player with the highest score

            # Формируем результаты
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

            # Удаляем игру из списка активных игр
            self.server.remove_game(self.id)
    
    def close_connection_players(self, players: List[Player]):
        for player in players:
            if player.socket:  # Проверяем, что сокет еще существует
                print(f"Close connection: {player.address[0]}: {player.address[1]}")
                try:
                    player.socket.close()
                    player.socket = None  # Устанавливаем сокет в None, чтобы избежать повторного закрытия
                except Exception as e:
                    print(f"Error closing socket for player {player.id}: {e}")

    def broadcast(self, message):
        """Send a message to all players"""
        if not isinstance(message, str):
            message = json.dumps(message)

        for player in self.players:
            try:
                if player.socket:  # Проверяем, что сокет еще существует
                    player.socket.send(message.encode())
                    print(f"Send message to {player.address[0]}: {player.address[1]}")
            except (ConnectionResetError, BrokenPipeError):
                print(f"Player {player.address[0]}:{player.address[1]} disconnected during broadcast.")
                self.handle_disconnect(player)
            except Exception as e:
                print(f"Error sending message to {player.address[0]}:{player.address[1]}: {e}")
                self.handle_disconnect(player)
    
    def handle_disconnect(self, player: Player):
        """Handle a player disconnecting"""
        with self.lock:
            if not player.socket:  # Проверяем, что сокет еще существует
                return
            
            if player in self.players:
                print(f"Close connection: {player.address[0]}:{player.address[1]}")
                self.players.remove(player)
                try:
                    player.socket.close()
                    player.socket = None  # Устанавливаем сокет в None, чтобы избежать повторного закрытия
                except Exception as e:
                    print(f"Error closing socket for player {player.id}: {e}")
                
                # Если все игроки отключились, завершаем игру
                if self.game_state == 'playing' and len(self.players) == 0:
                    self.end_game()
    
    
class Server:
    def __init__(self):
        self.games: Dict[int, Game] = {}
        self.next_game_id = 0
        self.next_player_id = 0
        self.buffer_size = 10000
        self.lock = threading.Lock()

    def createGame(self, player: Player) -> tuple[int, int]:
        ''' 
        The function is responsible for the creation of the game. 
        It returns game id (integer) 
        '''
        game_id = self.next_game_id
        self.next_game_id += 1
        game = Game(game_id, player, self)
        with self.lock:
            self.games[game_id] = game
        return game_id, player.id

    def connectGame(self, game_id: int, player: Player) -> tuple[int, int, list]:
        ''' 
        The function is responsible for connecting the player to the game. 
        It returns true if the connection was successful, otherwise false 
        '''
        game = self.games[game_id]
        if game is None:
            return (None, -1, [])
        player_id, list_players = game.handlePlayerConnect(player)
        return (game_id, player_id, list_players)

    def getMessage(self, client_socket: socket.socket) -> dict:
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
        with self.lock:
            player_id = self.next_player_id
            self.next_player_id += 1
        player = Player(client_socket, client_addr, player_id)
        print(f"New connection from {client_addr[0]}: {client_addr[1]}")

        # Waiting for a request from the newly connected player
        message = self.getMessage(client_socket)
        print(f"Got message from {client_addr[0]}: {client_addr[1]}:")

        # Create a room and generate a reply to the player if there was a request to create a room 
        if (message['type'] == 'create'): 
            game_id, player_id = self.createGame(player)
            answer = {
                "type": "status",
                "player_id": player_id,
                "game_id": game_id,
                "list_of_players": [player_id]
            }
            client_socket.send(json.dumps(answer).encode())
        # Connects the player to the room and generate a reply to the player.
        elif (message['type'] == 'connect'):
            game_id = int(message['game_id']) 
            game_id, player_id, list_players = self.connectGame(game_id, player)
        
        else:
            answer = {"type": "Error"}
    
            client_socket.send(json.dumps(answer).encode())
        
        player_thread = threading.Thread(
            target=self.listen_to_player,
            args=(player, game_id),
            daemon=True
        )
        player_thread.start()
        
        
        
    def listen_to_player(self, player: Player, game_id):
        """Listen to messages from a connected player"""
        game = self.games[game_id]
        while True:
            try:
                if not player.socket:  # Проверяем, что сокет еще существует
                    break
                # Получение сообщения от игрока
                message = self.getMessage(player.socket)
                print(f"Got message from {player.address[0]}:{player.address[1]}: {message}")

                # Обработка сообщений
                if message['type'] == 'ready to start':
                    game.handle_ready(player)
                elif message['type'] == 'answer':
                    print("Get answer")
                    game.process_answer(player, message['round'], message['answer'])
                else:
                    print(f"Unknown message type: {message['type']}")
                    
            except (ConnectionResetError, BrokenPipeError):
                print(f"Player {player.address[0]}:{player.address[1]} disconnected.")
                game.handle_disconnect(player)
                break
            except Exception as e:
                print(f"Error handling player {player.address[0]}:{player.address[1]}: {e}")
                game.handle_disconnect(player)
                break
            
    def remove_game(self, game_id: int):
        """Remove a game from the list of active games"""
        with self.lock:
            if game_id in self.games:
                print(f"Removing game {game_id}")
                del self.games[game_id]

    def serve(self, host, port, max_num_player):
        '''
        The function creates a socket, configures it, and starts listening for connections 
        '''
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(max_num_player)
        print(f"Server is listening on {host}:{port} ")
        self.manage_new_connection()

if (__name__ == '__main__'):
    server = Server()
    server.serve(HOST, PORT, 10)