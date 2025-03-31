<h4 align="center">
    Crazy Arcade <br>
    CMPT 371: Data Communication / Networking
    <div align="center">
    <br>
        <!-- <a href=".">
            <img src="https://github.com/sfuosdev/Website/actions/workflows/node.yml/badge.svg"/>
        </a> -->
    </div>
</h4>

<p align="center">
    <a href="#team-member">Team member</a> •
    <a href="#framework">Framework</a> •
    <a href="#contribution">Contribution</a>
</p>

### Team member

- Tommy Oh (301544525)
- Alex Chung (301549726)
- Parmveer Singh Nijjar (301563903)
- Munir Adam

### Framework

- This project is based on Python

- May use Pygame, or PyGUI, etc

# Cannon Chaos

## Overview  
**Cannon Chaos** is a **real-time online multiplayer game** where players compete in a grid-based arena, racing to control powerful cannons and eliminate opponents. The last player standing wins.  

The game follows a **client-server architecture**, where one player hosts the server, and all others connect as clients. Networking is implemented using **raw socket programming**, ensuring direct communication between players.  

## Gameplay Mechanics  

- The game takes place on a **square grid-based arena** with obstacles providing cover.  
- **Cannons spawn randomly** on the map, and players must race to reach them.  
- The first player to **reach a cannon gains exclusive control** (mutex lock).  
- Cannons have a **timed duration of use**—if the player doesn't fire within the time limit, they **explode**.  
- Each cannon has a **limited number of shots** before becoming inactive.  

### 🔥 Cannon Types  
- **Rapid Shot** – Fires fast but deals low damage.  
- **Explosive Shell** – Slow but has a large explosion radius.  
- **Bouncing Shot** – Ricochets off walls, hitting unexpected angles.  

### 🎯 Player Abilities  
- Players must **dodge, hide, and strategize** to avoid being shot.  
- **Dash ability** allows quick movement (short cooldown).  
- **Health bar** decreases when hit; players are eliminated when it reaches zero.  
- If two players try to grab the same cannon, a **quick reaction mini-game** (e.g., button mash) determines the winner.  

### ⚡ Game Flow Enhancements  
- **Power-ups** drop when a player is eliminated (e.g., speed boost, health pack).  
- **Sudden Death Mode** activates if the match lasts too long (faster cannon fire, shrinking map).  

## Winning Condition  
- The **last player alive wins the round**.  

## Technical Details  

- **Client-Server Model**  
  - One player starts the **server**, and all players (including the host) connect as **clients**.  
- **No External Game Networking Libraries**  
  - The backend is written using **raw socket programming** for player movement, cannon control, and game state synchronization.  
- **Simple 2D Graphics**  
  - The game uses **Pygame** for rendering, focusing on functionality over complexity.  

## Installation & Setup  
### Prerequisites  
- Python 3.x  
- Pygame (`pip install pygame`)  

### Running the Game  
1. Start the server:  
   ```sh
   python server.py

### Contribution

- placeholder
