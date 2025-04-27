import json
import socket
import threading
import time

# Изменить на действительные
SERVER_HOST = 'localhost'
SERVER_PORT = 20000

class ClientEntity:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_id = None
        self.game_id = None
        self.players = []
        self.running = True
        self.answer_timer = None
        self.current_round = -1
        self.colours = ["RED", "GREEN", "BLUE", "YELLOW", "BLACK", "WHITE", "PINK", "ORANGE", "PURPLE", "BROWN", "GREY", "CYAN", "MAROON", "LIME", "OLIVE", "AQUA", "FUCHSIA", "INDIGO", "VIOLET", "MAGENTO"]
        self.wait_answer = False

    def start(self):
        # ⭐️ UPD (TCP соединение)
        try:
            self.sock.connect((SERVER_HOST, SERVER_PORT))
        except ConnectionError as e:
            print(f"Ошибка подключения к серверу: {e}")
            self.running = False
            return
        
        print("Добро пожаловать в викторину!")
        print("1. Создать новую комнату")
        print("2. Присоединиться к существующей комнате")

        while True:
            choice = input("Выберите действие: ").strip()
            if choice == "1":
                self.create_game()
                break
            elif choice == "2":
                self.join_game()
                break
            else:
                print("Неверный выбор")

        receiver_thread = threading.Thread(target=self.receive_messages)
        receiver_thread.daemon = True
        receiver_thread.start()
    
    def get_name(self, ip):
        return f"{self.colours[ip % len(self.colours)]}_{ip}"

    def create_game(self):
        message = {"type": "create"}
        self.sock.send(json.dumps(message).encode())
        print("Создаем новую комнату...")

    def join_game(self):
        game_id = input("Введите ID комнаты: ").strip()
        message = {
            "type": "connect",
            "game_id": game_id
        }
        self.sock.send(json.dumps(message).encode())
        print(f"Пытаемся присоединиться к комнате {game_id}...")

    def handle_status(self, data):
        self.player_id = data["player_id"]
        self.game_id = data["game_id"]
        self.players = data["list_of_players"]
        
        if self.game_id is None:
            print("Ошибка: такой комнаты не существует")
            # ⭐️ UPD (повторная попытка подключения)
            self.join_game()
        else:
            # ⭐️ UPD (изменил id на цвет)
            print(f"Вы подключились к комнате {self.game_id} как игрок {self.get_name(self.player_id)}")
            # ⭐️ UPD (Вывел в одну строчку через запятую всех игроков, но вместо id показывал цвет)
            print(f"Текущие игроки в комнате: ", end="")
            for player_id in self.players:
                print(f"{self.get_name(player_id)}", end=" ")
            print()
            self.wait_for_ready()     # ⭐️ Непонятно будет ли он пока ждёт начала получать сообщения о новых игроках... (скорее всего все сообщения о новых игроках прийдут после нажатия "готов")

    def wait_for_ready(self):
        # ⭐️ UPD (обновил способ отправки "ready")
        wait = input("Нажмите ENTER когда будете готовы начать игру").strip()
        
        message = {"type": "ready to start"}
        self.sock.send(json.dumps(message).encode())
        print("Ожидаем других игроков...")

    def handle_new_player(self, data):
        # ⭐️ NEW (Добавил игрока в список)
        self.players.append(data["player_id"])
        print(f"\nНовый игрок подключился: {self.get_name(data['player_id'])}")

    def handle_question(self, data):
        self.current_round = data["round"]
        print(f"\nРаунд {self.current_round + 1}/5:")
        print(data["question"])
        for i, option in enumerate(data["options"]):            # ⭐️ проверить как эта строчка работает
            print(f"{i+1}. {option}")
        
        self.answer_timer = threading.Timer(10.0, self.send_timeout_answer)
        self.answer_timer.start()
        
        # ⭐️ UPD (добавлена проверка на корректность ответа)
        self.wait_answer = True
        while self.wait_answer:
            answer = input("Ваш ответ (1-4): ").strip()
            if answer in ["1", "2", "3", "4"]:
                self.wait_answer = False
            else:
                # ⭐️ UPD (чтоб формулировка одновременно подходила и под неправильный ввод и под окончание времени)
                print("Ответ не будет засчитан")    

        # ⭐️ UPD (добавил проверку, чтоб если чел "застрянет" в input и пока находится в нём сервер перейдёт на следующий раунд — не отправил ответ)
        if self.current_round != -1:
            self.send_answer(answer)

    def send_timeout_answer(self):
        if self.current_round != -1:  # Если раунд еще активен
            # ⭐️ UPD (изменил текст, чтоб человек при окончании раунда вышел из функции iput(), так как если останется — всё пойдёт по попе)
            print("\nВремя вышло! Нажмите ENTER")
            message = {
                "type": "answer",
                "round": self.current_round,
                "answer": None
            }
            self.sock.send(json.dumps(message).encode())
            self.current_round = -1
            self.wait_answer = False

    def send_answer(self, answer):
        if self.answer_timer and self.answer_timer.is_alive():
            self.answer_timer.cancel()
        
        answer_num = int(answer) - 1 
        # ⭐️ DEL (сделал проверку выше)
        
        message = {
            "type": "answer",
            "round": self.current_round,
            "answer": answer_num
        }
        self.sock.send(json.dumps(message).encode())
        self.current_round = -1
    
    def handle_correct_answer(self, data):
        print(f"\nПравильный ответ: {data['correct_answ']}")
        print("Ваш результат: ", "Верно" if data["your_res"] else "Неверно")
        print("Текущий счет:")
        for i, score in enumerate(data["curr_score"]):                                  # ⭐️ сделать красивую табличку + измеить число на цвет
            #print(f"Игрок {i}: {score} очков")  
            # ⭐️ UPD (нужно проверить в каком порядке сервер отправляет результаты)
            print(f"Игрок {self.get_name(self.players[i])}: {score} очков")

    def handle_end_game(self, data):
        print("\nИгра окончена!")
        print("Финальный счет:")
        max_score = max(data["curr_score"])
        winners = [i for i, score in enumerate(data["curr_score"]) if score == max_score]   # ⭐️ проверить как эта строчка работает
        
        for i, score in enumerate(data["curr_score"]):                                  # ⭐️ сделать красивую табличку + измеить число на цвет
            #print(f"Игрок {i}: {score} очков")  
            # ⭐️ UPD (нужно проверить в каком порядке сервер отправляет результаты)
            print(f"Игрок {self.get_name(self.players[i])}: {score} очков")
        
        if len(winners) == 1:
            print(f"Победил игрок {winners[0]}!")
        else:
            print("Ничья между игроками:", ", ".join(map(str, winners)))
        
        self.running = False

    def receive_messages(self):
        while self.running:
            try:
                data = self.sock.recv(8192)      # изменить буфер
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
                print("Ошибка декодирования сообщения от сервера") # возможно надо отослать серверу?
            except ConnectionResetError:
                print("Соединение с сервером разорвано")
                self.running = False
            except Exception as e:
                print(f"Неизвестная ошибка: {e}")
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
        print("\nИгра прервана пользователем")
    finally:
        client.cleanup()

if __name__ == "__main__":
    main()
