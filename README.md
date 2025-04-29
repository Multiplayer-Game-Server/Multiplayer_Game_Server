# 🎮 TCP Quiz in Python

Multiuser quiz with a Python server using sockets. Players answer questions related to it industry and compete for the best result.
## 🔍 Description
- [📄 About the project](#-about-the-project): in this section you will find a brief description of the project.
- [🚀 Project features](#-project-features): in this section you will find the specifics of the project implementation 
- [🎯 Game Mechanics](#-game-mechanics): in this section you will find the features of the game's implementation.
- [⚙️ Requirements](#%EF%B8%8F-requirements): in this section you will find the necessary resources that must be installed in order for the program to work.
- [💿 How to use the program](#-how-to-use-the-program): in this section you will find a description of how to start the server and how to start the game, as well as how to use the game.

## 📄 About the project
The project was created as part of an academic project activity in which students demonstrate their proficiency with sockets in Python, threads in Python, and synchronizing multiple clients and a server.

## 🚀 Project features
- Client-server communication is implemented in the project.
- The program works on TCP protocol of transport level.
- Terminal Game.
- Default server settings:
    - **ip adress:** 0.0.0.0
    - **Port:** 20250
    - **Total number of clients the server can handle:** 25
    - *(Parameters can be modified inside the server.py file)*
- Default client settings:
    - **ip address to connect to:** 127.0.0.1
    - **Port to connect to:** 20250
    - *(Parameters can be modified inside the client.py file)*
      
## 🎯 Game Mechanics
- Each game consists of 5 rounds.
- Each round contains 4 options of answers.
- Each question is given 30 seconds to answer.
- The game automatically calculates player rankings.
- Each player has a unique nickname with color.

## ⚙️ Requirements
- Python 3.7+
- No additional requirements 

## 💿 How to use the program
### Server side:
- Download the project from github
```bash
git clone https://github.com/Multiplayer-Game-Server/Multiplayer_Game_Server.git
cd ./Multiplayer_Game_Server
```
- Start a server on one of the host
```bash
python ./server.py
```

### Client side:
Only the *client.py* file is required.
All players should have *client.py* file.
- Download the project from github
```bash
git clone https://github.com/Multiplayer-Game-Server/Multiplayer_Game_Server.git
cd ./Multiplayer_Game_Server
```
- Start a client on one of the host
```bash
python ./client.py
```
- If the connection to the server is successful, you will be offered a choice of 2 functions: 
    * **Create Game:** selecting this option creates a new game that new players can join.
    * **Connect to the game:** when this option is selected, the player is prompted to enter the id of the room he wants to connect to. If the connection is successful, he will be added to the room
- After you have connected to the room, you can wait for new players or press ENTER to switch to ready status. 
- After all players are ready, the round begins with a question and 4 answer choices. Use the numbers 1-4 to choose the answer. After the timer expires or after everyone has answered, the terminal will display the rating, the result of your answer and the next question. 
- After 5 rounds the winner will be declared and the game will automatically end.
