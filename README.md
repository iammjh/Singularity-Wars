# Singularity Wars

Singularity Wars is a 3D space combat game built with OpenGL where players pilot a spaceship through an infinite procedurally-generated universe. Battle alien pirates, navigate gravitational anomalies, and upgrade your ship to survive increasingly difficult waves of enemies.

## Description

Embark on an endless space adventure featuring:
- Free-roam 3D space exploration with dynamic hazards and enemies
- Upgradeable ship and weapons earned through combat and exploration
- Multiple difficulty levels and dynamic scaling
- Immersive first-person and third-person camera modes
- Physics-based movement and gravitational effects

## Features

### Combat System
- **Alien Pirates**: Enemy ships that pursue and attack the player; they can fire projectiles and are immune to space rock damage
- **Weapon Upgrades**: Unlock enhanced weapons by defeating enemies with increased damage, faster fire rate, and special effects
- **Auto-aim Assist**: Smart targeting system to help engage enemies
- **Multiple Gun Levels**: Progressive weapon upgrades as you eliminate more enemies

### Space Hazards
- **Space Rocks**: Randomly spawning asteroids in unexplored regions that damage ships on collision, block bullets, and can be destroyed
- **Black Holes**: Exert gravitational pull on nearby objects; larger black holes have stronger attraction and can damage ships
- **White Holes**: Repel nearby objects and alter ship trajectories
- **Wormholes**: Instantly transport players to unexplored regions and grant upgrade points

### Gameplay Mechanics
- **Free 6-DOF Movement**: Navigate in all directions across a vast 3D space (5000x5000x1200 units)
- **Physics-Based Flight**: Realistic acceleration, drag, and momentum
- **Ship Upgrades**: Enhance speed and hit points by defeating enemies, destroying asteroids, and traveling through wormholes
- **Dynamic Difficulty**: Game scales with player score, spawning tougher and more numerous enemies over time
- **Difficulty Settings**: Choose between Easy, Normal, and Hard modes
- **Camera Views**: Toggle between first-person and third-person perspectives
- **Scoreboard**: Track top 5 high scores and last round performance

### Visual Effects
- Damage flash effects when taking hits
- Shield pulse animations
- Particle systems for explosions and environmental effects
- Dynamic lighting and atmospheric rendering

## Files

- `Singularity War.py` — Main game file containing all game logic and rendering
- `Singularity-Wars.spec` — PyInstaller configuration for building executables
- `build/` — Build artifacts from PyInstaller

## Requirements

- **Python**: 3.8 or higher
- **PyOpenGL**: OpenGL bindings for Python
  ```
  pip install PyOpenGL PyOpenGL-accelerate
  ```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/mrjahid11/Singularity-Wars.git
   cd Singularity-Wars
   ```

2. **Install dependencies**:
   ```bash
   pip install PyOpenGL PyOpenGL-accelerate
   ```

   Or if using a virtual environment (recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   # source .venv/bin/activate  # On Linux/Mac
   pip install PyOpenGL PyOpenGL-accelerate
   ```

## How to Run

From the repository root, run:

```bash
python "Singularity War.py"
```

The game will open in a new window. Use the controls below to play.

## Controls

### Movement
- **W/S**: Move forward/backward
- **A/D**: Move left/right
- **Q/E**: Move down/up (Z-axis)
- **Arrow Keys**: Rotate ship direction

### Game Controls
- **Spacebar**: Fire weapons
- **V**: Toggle camera view (first-person/third-person)
- **P**: Pause/Resume game
- **R**: Restart game (when game over)
- **ESC**: Quit game

### Menu Controls
- **1**: Easy difficulty
- **2**: Normal difficulty
- **3**: Hard difficulty
- **Enter**: Start game

## Gameplay Tips

- Keep moving to avoid enemy fire and gravitational hazards
- Use auto-aim to help target distant enemies
- Black holes can be deadly but also useful for pulling enemies in
- Wormholes provide valuable upgrade points—seek them out
- Balance between offense and evasion as difficulty increases
- Watch your health indicator and shield status
- First-person view offers better immersion, third-person offers better situational awareness

## Building Executable

The project includes a PyInstaller spec file for creating standalone executables:

```bash
pip install pyinstaller
pyinstaller "Singularity-Wars.spec"
```

The executable will be created in the `dist/` directory.

## Project Structure

```
Singularity-Wars/
├── Singularity War.py          # Main game file
├── Singularity-Wars.spec       # PyInstaller build configuration
├── README.md                   # This file
├── LICENSE                     # MIT License
└── build/                      # Build artifacts (generated)
```

## Technical Details

- **Graphics**: OpenGL for 3D rendering
- **Physics**: Custom implementation for movement, gravity, and collisions
- **World Size**: 5000x5000x1200 units of explorable space
- **Procedural Generation**: Dynamic spawning of enemies, asteroids, and phenomena
- **Performance**: Optimized for smooth gameplay with multiple entities

## Credits

Developed as part of CSE423 coursework.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
