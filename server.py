import socket

HOST = '0.0.0.0'
PORT = 20250

class Game:
    def __init__(self, id):
        self.id = id

    def handlePlayerConnect(self, player):
        pass

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