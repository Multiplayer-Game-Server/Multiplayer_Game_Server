import json
import socket
import sys
import threading
import time

if sys.platform == "win32":
    import msvcrt
else:
    import select

import os
if sys.platform == "win32":
    os.system(f'mode con: cols=52 lines=35')
else:  # Linux/macOS
    print("\x1b[8;35;52t")

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 20250

class ClientEntity:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.game_id = None
        self.players = []
        self.running = True
        self.answer_timer = None
        self.current_round = -1
        self.colours = ["RED", "BLUE", "GREEN", "YELLOW", "PINK", "WHITE", "BLACK", "ORANGE", "CYAN", "LIME", "GREY", "CORAL", "BROWN", "AMBER", "OLIVE", "AQUA", "LAVA", "INDIGO", "RUST", "IVORY"]
        self.wait_ready = True
        self.final_answer = None
        self.last_answer = None
        self.prev_results = {}
        self.all_marks = [None, None, None, None, None]

    def start(self):
        # ⭐️ UPD (TCP соединение)
        try:
            self.sock.connect((SERVER_HOST, SERVER_PORT))
        except ConnectionError as e:
            print(f"Ошибка подключения к серверу: {e}")
            self.running = False
            return

        print("┌─ - - - - - - - - - - - - - - - - - - - - - - - ─ ┐")
        for i in range (33):
            print("|                                                  |")   
        print("└─ - - - - - - - - - - - - - - - - - - - - - - - ─ ┘")
        print()
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
                self.create_game()
                break
            elif choice == "2":
                self.join_game()
                break
            else:
                print("❌ Invalid choice. Please enter '1' or '2'")

        receiver_thread = threading.Thread(target=self.receive_messages)
        receiver_thread.daemon = True
        receiver_thread.start()
    
    def get_name(self, ip):
        return f"{self.colours[ip % len(self.colours)]}_{ip}"

    def create_game(self):
        message = {"type": "create"}
        self.sock.send(json.dumps(message).encode())

    def join_game(self):
        # ⭐️ UPD (пеперместил input)
        game_id = input("Enter room ID: ").strip()
        message = {
            "type": "connect",
            "game_id": game_id
        }
        self.sock.send(json.dumps(message).encode())

    def handle_status(self, data):
        self.player_id = data["player_id"]
        self.game_id = data["game_id"]
        self.players = data["list_of_players"]
        
        if self.game_id is None:
            print("\nSorry, room does not exist... Try again.")
            # ⭐️ UPD (повторная попытка подключения)
            self.join_game()
        else:
            names = [self.get_name(player_id) for player_id in self.players]
            
            print()
            print("┌─────────────┬───────┬─────────────┬──────────────┐")
            print(f"│   Room ID   │{self.game_id:^7}│  Your Name  │{self.get_name(self.player_id):^14}│")
            print("└─────────────┴───────┴─────────────┴──────────────┘")
            print("👥 Current players: ", ", ".join(map(str, names)))
            print()

            self.wait_for_ready()

    def wait_for_ready(self):
        def receive_players():
            try:
                while self.wait_ready:
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

        self.wait_ready = True
        thread = threading.Thread(target=receive_players)
        thread.start()

        input("Press ENTER to get READY\n").strip()


        self.wait_ready = False

        message = {"type": "ready to start"}
        self.sock.send(json.dumps(message).encode())
        print("⏳ Waiting for other players to be ready...\n")

        thread.join()

    def handle_new_player(self, data):
        # ⭐️ NEW (Добавил игрока в список)
        self.players.append(data["player_id"])
        print(f"\n▶︎ New player joined: {self.get_name(data['player_id'])}")

    def handle_question(self, data):
        self.current_round = data["round"]
        print("\n"*23)
        print(f"\n\n\n\n\n\n\n\n\n================= 🎯 ROUND {self.current_round + 1}/5 🎯 ==================")
        print(data["question"])
        print("====================================================")
        for i, option in enumerate(data["options"]):
            print(f"{i+1}. {option}")
        print()

        self.final_answer = None

        def input_thread():

            # ⭐️ Windows: use "msvcrt"
            if sys.platform == "win32":
                print("⌛ Press 1-4 within 30 seconds:")
                start_time = time.time()
                while True:
                    if msvcrt.kbhit():  # ⭐️ Проверяем, есть ли ввод
                        answer = msvcrt.getch().decode()
                        if answer in ["1", "2", "3", "4"]:
                            self.final_answer = answer
                            print("Your answer: " + answer)
                            break
                        else:
                            print("❌ Invalid answer, not accepted")
                            break
                    
                    # ⭐️ Проверяем таймаут 30 сек
                    if time.time() - start_time > 30:
                        print("⏰ Time's up! Answer not accepted.")
                        break

            # ⭐️ Unix (Mac/Linux): use "select"
            else:
                print("⌛ Enter your answer within 30 seconds (1-4):")
                rlist, _, _ = select.select([sys.stdin], [], [], 30.0)
                if not rlist:
                    print("⏰ Time's up! Answer not accepted.")
                    return

                answer = sys.stdin.readline().rstrip('\n')
                if answer in ["1", "2", "3", "4"]:
                    self.final_answer = answer
                    print("Your answer: " + answer)
                else:
                    print("❌ Invalid answer, not accepted")

        thread = threading.Thread(target=input_thread)
        thread.daemon = True
        thread.start()
        thread.join()
        print("====================================================")
        
        if self.final_answer is None:
            self.send_timeout_answer()
        else:
            self.send_answer(self.final_answer)

    def send_timeout_answer(self):
        message = {
            "type": "answer",
            "round": self.current_round,
            "answer": None
        }
        self.sock.send(json.dumps(message).encode())
        self.last_answer = None

    def send_answer(self, answer):
        answer_num = int(answer) - 1 
        self.last_answer = answer_num + 1
        
        message = {
            "type": "answer",
            "round": self.current_round,
            "answer": answer_num
        }
        self.sock.send(json.dumps(message).encode())
    
    def handle_correct_answer(self, data):
        correct_answ = data["correct_answ"]
        curr_score = data["curr_score"]
        deleted_players = data["deleted_players"]
        
        # ⭐️ Определяем, правильно ли ответил клиент
        if (self.last_answer != None):
            your_res = self.last_answer == correct_answ  # ⭐️ Сравниваем последний ответ клиента с правильным ответом
        else:
            your_res = False
        if self.last_answer == None:
            y_ans = "–"
        else:
            y_ans = self.last_answer
        if your_res:
            res = "✅"
        else:
            res = "❌"
        print()
        print("┌─────────────┬───┬────────────────┬───┬────────┬──┐")
        print(f"│ Your Answer │ {y_ans:^1} │ Correct Answer │ {correct_answ:^1} │ Result │{res}│")
        print("└─────────────┴───┴────────────────┴───┴────────┴──┘")
        print()
        # ⭐️ Удалить удалённых игроков из списка игроков
        if deleted_players != None:
            for pair in deleted_players:
                player_id = pair['id']
                if player_id in self.players:
                    self.players.remove(player_id)
        
        mark_res = {}
        if self.current_round == 0:
            for i, score in enumerate(curr_score):
                if score == 0:
                    mark_res[self.players[i]] = "❌"
                else:
                    mark_res[self.players[i]] = "✅"
            if deleted_players:
                for pair in deleted_players:
                    if pair['score'] == 0:
                        mark_res[pair['id']] = "❌"
                    else:
                        mark_res[pair['id']] = "✅"
        else:
            for i, score in enumerate(curr_score):
                if self.prev_results[self.players[i]] == score:
                    mark_res[self.players[i]] = "❌"
                else:
                    mark_res[self.players[i]] = "✅"
            if deleted_players:
                for pair in deleted_players:
                    if self.prev_results[pair['id']] == pair['score']:
                        mark_res[pair['id']] = "❌"
                    else:
                        mark_res[pair['id']] = "✅"
        self.all_marks[self.current_round] = mark_res
        
        for i, score in enumerate(curr_score):
            self.prev_results[self.players[i]] = score
        if deleted_players:
            for pair in deleted_players:
                self.prev_results[pair['id']] = pair['score']

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
        print("\n\n\n")
        print("- - - - - - - - - - - - - - - - - - - - - - - - - - ")
        print("🏁                The Game Is Over!               🏁")
        print("- - - - - - - - - - - - - - - - - - - - - - - - - - ")
        print()
        max_score = max(data["curr_score"])
        winners = [i for i, score in enumerate(data["curr_score"]) if score == max_score]
        
        if len(winners) == 1:
            print(f"               🏆 Player {self.get_name(self.players[winners[0]])} WIN!\n\n")
        else:
            for i in winners:
                winners[i] = self.get_name(self.players[i])
            print("🏆 Draw Between:", ", ".join(map(str, winners)))
            print()
        
        self.running = False

    def receive_messages(self):
        while self.running:
            try:
                data = self.sock.recv(8192)
                if not data:
                    break
                message = json.loads(data.decode())
                
                if message["type"] == "status":
                    self.handle_status(message)
                elif message["type"] == "new player":
                    self.handle_new_player(message)
                elif message["type"] == "question":
                    self.handle_question(message)
                elif message["type"] == "correct answer":
                    self.handle_correct_answer(message)
                elif message["type"] == "end game":
                    self.handle_end_game(message)
                
            except json.JSONDecodeError:
                print("Failed to decode server message")
            except ConnectionResetError:
                print("Connection to server lost")
                self.running = False
            except Exception as e:
                self.running = False

    def cleanup(self):
        if self.answer_timer and self.answer_timer.is_alive():
            self.answer_timer.cancel()
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
