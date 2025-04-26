import json
import socket
import threading
import time

# Изменить на действительные
SERVER_HOST = 'localhost'
SERVER_PORT = 20000
CLIENT_PORT = 10000

class ClientEntity:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', CLIENT_PORT))
        self.player_id = None
        self.game_id = None
        self.players = []
        self.running = True
        self.answer_timer = None
        self.current_round = -1
        self.colours = ["RED", "GREEN", "BLUE", "YELLOW", "BLACK", "WHITE", "PINK", "ORANGE", "PURPLE", "BROWN", "GREY", "CYAN", "MAROON", "LIME", "OLIVE", "AQUA", "FUCHSIA", "INDIGO", "VIOLET", "MAGENTO"]
        self.wait_answer = False

    def start(self):
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
        self.sock.sendto(json.dumps(message).encode(), (SERVER_HOST, SERVER_PORT))
        print("Создаем новую комнату...")

    def join_game(self):
        game_id = input("Введите ID комнаты: ").strip()
        message = {
            "type": "connect",
            "game_id": game_id
        }
        self.sock.sendto(json.dumps(message).encode(), (SERVER_HOST, SERVER_PORT))
        print(f"Пытаемся присоединиться к комнате {game_id}...")

    def receive_messages(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(8192)      # изменить буфер
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