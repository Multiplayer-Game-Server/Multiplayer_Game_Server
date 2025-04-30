import json
import socket
import sys
import threading
import time

# Windows: "msvcrt", Linux/MacOS: "select" (this is for non-blocking input)
if sys.platform == "win32":
    import msvcrt
else:
    import select

# Set the size of the terminal for a comfortable game
import os
if sys.platform == "win32":
    os.system(f'mode con: cols=52 lines=35')
else:
    print("\x1b[8;35;52t")

# Adress of the server
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 20250

class ClientEntity:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.game_id = None
        self.players = []
        self.running = True
        self.current_round = -1
        self.colours = ["RED", "BLUE", "GREEN", "YELLOW", "PINK", "WHITE", "BLACK", "ORANGE", "CYAN", "LIME", "GREY", "CORAL", "BROWN", "AMBER", "OLIVE", "AQUA", "LAVA", "INDIGO", "RUST", "IVORY"]
        self.wait_ready = True
        self.final_answer = None
        self.last_answer = None
        self.prev_results = {}
        self.all_marks = [None, None, None, None, None]

    def start(self):
        '''Function for printing the starting information to the user'''
        try:
            # Connect to the server
            self.sock.connect((SERVER_HOST, SERVER_PORT))
        except ConnectionError as e:
            print(f"Error connecting to server: {e}")
            self.running = False
            return

        # Print rectangle that using for customize the size of the terminal
        print("┌─ - - - - - - - - - - - - - - - - - - - - - - - ─ ┐")
        for i in range (33):
            print("|                                                  |")   
        print("└─ - - - - - - - - - - - - - - - - - - - - - - - ─ ┘")
        print()
        # Print welcome message and menu
        print("====================================================")
        print("✨          WHO WANTS TO BE A PROGRAMMER          ✨")
        print("====================================================")
        print()
        print("                Welсome, New Player!                ")
        print()
        print("For a comfortable game, connect the borders of the  terminal with the borders of the rectangle above.")
        print()
        print("Choose an option:")
        print("1. Create a new game room")
        print("2. Join an existing room\n")

        while True:
            choice = input("Your choose: ").strip()
            if choice == "1":
                # create game room
                self.create_game()
                break
            elif choice == "2":
                # join game to existing game
                self.join_game()
                break
            else:
                print("❌ Invalid choice. Please enter '1' or '2'")

        # Create a thread for receiving all messages from the server
        receiver_thread = threading.Thread(target=self.receive_messages)
        receiver_thread.daemon = True
        receiver_thread.start()
    
    def get_name(self, ip):
        '''Function for getting the uniquename for the player by it's ID'''
        return f"{self.colours[ip % len(self.colours)]}_{ip}"

    def create_game(self):
        '''Function for creating a new game room by sending a json message to the server'''
        message = {"type": "create"}
        self.sock.send(json.dumps(message).encode())

    def join_game(self):
        '''Function for joining an existing game room by sending a json message to the server'''
        game_id = input("Enter room ID: ").strip()
        message = {
            "type": "connect",
            "game_id": game_id
        }
        self.sock.send(json.dumps(message).encode())

    def handle_status(self, data):
        '''Function that recieve data from the server about assigned to player ID, about room ID, and list of IDs of all players'''
        self.player_id = data["player_id"]
        self.game_id = data["game_id"]
        self.players = data["list_of_players"]
        
        if self.game_id is None:
            print("\nSorry, room does not exist... Try again.")
            # Try to join another room in case of incorrect room ID
            self.join_game()
        else:
            names = [self.get_name(player_id) for player_id in self.players]
            
            # Print information about the player's ID, rooms's ID and list of players in the room
            print()
            print("┌─────────────┬───────┬─────────────┬──────────────┐")
            print(f"│   Room ID   │{self.game_id:^7}│  Your Name  │{self.get_name(self.player_id):^14}│")
            print("└─────────────┴───────┴─────────────┴──────────────┘")
            print("👥 Current players: ", ", ".join(map(str, names)))
            print()

            # Wait till the user will be ready to start the game
            self.wait_for_ready()

    def wait_for_ready(self):
        '''Function for waiting till the user will be ready to start the game. And handle messages from the server about new players, that join to the game room'''
        def receive_players():
            try:
                while self.wait_ready:
                    # Receive messages from the server
                    data = self.sock.recv(8192)
                    if not data:
                        break
                    message = json.loads(data.decode())
                    if message["type"] == "new player":
                        self.handle_new_player(message)
                    elif message["type"] == "question":
                        self.handle_question(message)
                    else:
                        print("Вы попали...")
            except Exception as e:
                self.running = False

        # Start thread for receiving new players
        self.wait_ready = True
        thread = threading.Thread(target=receive_players)
        thread.start()

        # Wait till the user will be ready
        input("Press ENTER to get READY\n").strip()

        # Stop receiving new players
        self.wait_ready = False

        # Send message to the server about readiness
        message = {"type": "ready to start"}
        self.sock.send(json.dumps(message).encode())
        print("⏳ Waiting for other players to be ready...\n")

        thread.join()

    def handle_new_player(self, data):
        '''Function for handling messages from the server about new players, that join to the game room'''
        self.players.append(data["player_id"])
        print(f"\n▶︎ New player joined: {self.get_name(data['player_id'])}")

    def handle_question(self, data):
        '''Function for recieving questions from the server and sending user's answers to the server'''
        self.current_round = data["round"]

        # Print the question and options
        print("\n"*23)
        print(f"\n\n\n\n\n\n\n\n\n================= 🎯 ROUND {self.current_round + 1}/5 🎯 ==================")
        print(data["question"])
        print("====================================================")
        for i, option in enumerate(data["options"]):
            print(f"{i+1}. {option}")
        print()

        self.final_answer = None

        def input_thread():
            '''Function for getting user's answer by non-blocking input. To achieve this function uses "select" and "msvcrt" modules for Windows and Unix respectively'''

            # Windows: use "msvcrt" (this is for non-blocking input)
            if sys.platform == "win32":
                print("⌛ Press 1-4 within 30 seconds:")
                start_time = time.time()
                while True:
                    # "msvcrt.kbhit()" returns True if there is any input in the buffer
                    if msvcrt.kbhit():
                        # "msvcrt.getch()" returns one character from the buffer
                        answer = msvcrt.getch().decode()
                        if answer in ["1", "2", "3", "4"]:
                            self.final_answer = answer
                            print("Your answer: " + answer)
                            break
                        else:
                            print("❌ Invalid answer, not accepted")
                            break
                    
                    # Check if the time has exceeded (basically there are 30 seconds to answer)
                    if time.time() - start_time > 30:
                        print("⏰ Time's up! Answer not accepted.")
                        break

            # Unix (Mac/Linux): use "select" (this is for non-blocking input)
            else:
                print("⌛ Enter your answer within 30 seconds (1-4):")
                # "select" is used to check if there is any input in the buffer with timeout of 30 seconds
                rlist, _, _ = select.select([sys.stdin], [], [], 30.0)
                # If there is no input in the buffer for 30 seconds —> time's up
                if not rlist:
                    print("⏰ Time's up! Answer not accepted.")
                    return
                # If there is input in the buffer —> get it
                answer = sys.stdin.readline().rstrip('\n')
                if answer in ["1", "2", "3", "4"]:
                    self.final_answer = answer
                    print("Your answer: " + answer)
                else:
                    print("❌ Invalid answer, not accepted")

        # Start thread for non-blocking input 
        thread = threading.Thread(target=input_thread)
        thread.daemon = True
        thread.start()
        thread.join()
        print("====================================================")
        
        if self.final_answer is None:
            # If the user didn't answer within 30 seconds —> send timeout answer
            self.send_timeout_answer()
        else:
            # If the user answered within 30 seconds —> send answer
            self.send_answer(self.final_answer)

    def send_timeout_answer(self):
        '''Function for sending json message to tell about timeout to the server'''
        message = {
            "type": "answer",
            "round": self.current_round,
            "answer": None
        }
        self.sock.send(json.dumps(message).encode())
        self.last_answer = None

    def send_answer(self, answer):
        '''Function for sending json message to tell about user's answer to the server'''
        answer_num = int(answer) - 1 
        self.last_answer = answer_num + 1
        
        message = {
            "type": "answer",
            "round": self.current_round,
            "answer": answer_num
        }
        self.sock.send(json.dumps(message).encode())
    
    def handle_correct_answer(self, data):
        '''Function for recieving correct answer from the server'''
        correct_answ = data["correct_answ"]
        curr_score = data["curr_score"]
        deleted_players = data["deleted_players"]
        
        # Check that the answer is correct by comparing users answer with the correct answer from the server
        if (self.last_answer != None):
            your_res = self.last_answer == correct_answ
        else:
            your_res = False
        # Check that the answer was giver (not None)
        if self.last_answer == None:
            y_ans = "–"
        else:
            y_ans = self.last_answer
        # If the answer is correct —> print "✅", else "❌"
        if your_res:
            res = "✅"
        else:
            res = "❌"
        # Print the result
        print()
        print("┌─────────────┬───┬────────────────┬───┬────────┬──┐")
        print(f"│ Your Answer │ {y_ans:^1} │ Correct Answer │ {correct_answ:^1} │ Result │{res}│")
        print("└─────────────┴───┴────────────────┴───┴────────┴──┘")
        print()
        # If some players were disconnected from the game room —> remove them from the list of players
        if deleted_players != None:
            for pair in deleted_players:
                player_id = pair['id']
                if player_id in self.players:
                    self.players.remove(player_id)
        
        # save the results of the current round
        mark_res = {}
        if self.current_round == 0:                     # if it's the first round
            for i, score in enumerate(curr_score):      # for each online player
                if score == 0:
                    mark_res[self.players[i]] = "❌"
                else:
                    mark_res[self.players[i]] = "✅"
            if deleted_players:                         # for each disconnected player
                for pair in deleted_players:
                    if pair['score'] == 0:
                        mark_res[pair['id']] = "❌"
                    else:
                        mark_res[pair['id']] = "✅"
        else:                                           # if it's not the first round
            for i, score in enumerate(curr_score):      # for each online player
                if self.prev_results[self.players[i]] == score:     # score changed -> mark "❌", else "✅"
                    mark_res[self.players[i]] = "❌"
                else:
                    mark_res[self.players[i]] = "✅"
            if deleted_players:                         # for each disconnected player
                for pair in deleted_players:
                    if self.prev_results[pair['id']] == pair['score']:
                        mark_res[pair['id']] = "❌"
                    else:
                        mark_res[pair['id']] = "✅"
        # save the results of the round for the futher use
        self.all_marks[self.current_round] = mark_res
        
        # update the list of scores with current data for using it in the next round to compare with the new scores and understand which players earned points
        for i, score in enumerate(curr_score):
            self.prev_results[self.players[i]] = score
        if deleted_players:
            for pair in deleted_players:
                self.prev_results[pair['id']] = pair['score']

        # print the current results
        print("┌──────────────────────────────────────────────────┐")
        print("│                 CURRENT RESULTS                  │")
        print("├──────────────┬────┬────┬────┬────┬────┬──────────┤")
        for i, score in enumerate(curr_score):
            print(
                f"│{self.get_name(self.players[i]):^14}│ "
                f"{'--' if self.all_marks[0] is None else self.all_marks[0][self.players[i]]} │ "
                f"{'--' if self.all_marks[1] is None else self.all_marks[1][self.players[i]]} │ "
                f"{'--' if self.all_marks[2] is None else self.all_marks[2][self.players[i]]} │ "
                f"{'--' if self.all_marks[3] is None else self.all_marks[3][self.players[i]]} │ "
                f"{'--' if self.all_marks[4] is None else self.all_marks[4][self.players[i]]} │"
                f"{score:^10}│"
            )
            if i != len(curr_score) - 1:
                print("├──────────────┼────┼────┼────┼────┼────┼──────────┤")
            elif i == len(curr_score) - 1 and not deleted_players:
                print("└──────────────┴────┴────┴────┴────┴────┴──────────┘")
            else:
                print("├──────────────┴────┴────┴────┴────┴────┴──────────┤") 
        # print the disconnected players in case if they are exist
        if deleted_players:
            print("│              DISCONNECTED PLAYERS                │")
            print("├──────────────┬────┬────┬────┬────┬────┬──────────┤")
            for pair in deleted_players:
                print(
                    f"│{self.get_name(pair['id']):^14}│ "
                    f"{'--' if self.all_marks[0] is None else self.all_marks[0][pair['id']]} │ "
                    f"{'--' if self.all_marks[1] is None else self.all_marks[1][pair['id']]} │ "
                    f"{'--' if self.all_marks[2] is None else self.all_marks[2][pair['id']]} │ "
                    f"{'--' if self.all_marks[3] is None else self.all_marks[3][pair['id']]} │ "
                    f"{'--' if self.all_marks[4] is None else self.all_marks[4][pair['id']]} │"
                    f"{pair['score']:^10}│"
                )
                if deleted_players.index(pair) != len(deleted_players) - 1:
                    print("├──────────────┼────┼────┼────┼────┼────┼──────────┤")
                elif deleted_players.index(pair) == len(deleted_players) - 1:
                    print("└──────────────┴────┴────┴────┴────┴────┴──────────┘")

    def handle_end_game(self, data):
        '''Function for recieving the end game message with data about final scores of players'''
        # print the end game message
        print("\n\n\n")
        print("- - - - - - - - - - - - - - - - - - - - - - - - - - ")
        print("🏁                The Game Is Over!               🏁")
        print("- - - - - - - - - - - - - - - - - - - - - - - - - - ")
        print()
        # find the winner/winners
        max_score = max(data["curr_score"])
        winners = [i for i, score in enumerate(data["curr_score"]) if score == max_score]
        
        # print the winner/winners
        if len(winners) == 1:
            print(f"               🏆 Player {self.get_name(self.players[winners[0]])} WIN!\n\n")
        else:
            for i in winners:
                winners[i] = self.get_name(self.players[i])
            print("🏆 Draw Between:", ", ".join(map(str, winners)))
            print()
        
        self.running = False

    def receive_messages(self):
        '''Function for recieving ALL messages from the server'''
        buffer = b""
        while self.running:
            try:
                # Receive data from the server
                data = self.sock.recv(8192)
                if not data:
                    break
                
                buffer += data
                
                # Process all complete messages in the buffer and split them by "\n"
                while b'\n' in buffer:
                    message_part, buffer = buffer.split(b'\n', 1)
                    if not message_part:
                        continue
                        
                    try:
                        message = json.loads(message_part.decode())
                        
                        # Handle messages
                        if message["type"] == "status":
                            self.handle_status(message)             # To get response after creating new game room or joining to existing
                        elif message["type"] == "new player":
                            self.handle_new_player(message)         # To get message about new player, that join to the game room
                        elif message["type"] == "question":
                            self.handle_question(message)           # To get question information from the server
                        elif message["type"] == "correct answer":
                            self.handle_correct_answer(message)     # To get message about correct answer
                        elif message["type"] == "end game":
                            self.handle_end_game(message)           # To get message about end game
                            
                    except json.JSONDecodeError as e:
                        print(f"Failed to decode server message: {e}")
                        print(f"Raw message: {message_part}")
                        self.running = False
                        break
                        
            except ConnectionResetError:
                print("Connection to server lost")
                self.running = False
            except Exception as e:
                print(f"Unexpected error: {e}")
                self.running = False

    def cleanup(self):
        '''Function for closing the socket'''
        self.sock.close()

def main():
    client = ClientEntity()
    try:
        client.start()
        while client.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🚫 Game interrupted by user")
    finally:
        client.cleanup()

if __name__ == "__main__":
    main()
