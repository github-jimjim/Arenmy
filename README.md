# ArenMy

ArenMy is a chess application that allows you to play against UCI-compatible chess engines. The project features a graphical interface to visualize the board, interact with the game, and evaluate positions using chess engines. It also supports adding custom engines for personalized experiences.

## Features

- **Chess Board Display**: A graphical chess board drawn with the ability to scale the board for different screen sizes.
- **Engine Integration**: Play against UCI-compatible engines by selecting engines from a list.
- **Move Evaluation**: Displays real-time evaluation from a selected engine.
- **Interactive Interface**: Click to make moves and play the game, with animations for engine moves.
- **Custom Engine Support**: Add custom engines and manage them through a simple UI.

## Requirements

- Python 3.x
- Tkinter
- PyYAML
- Pillow
- Python Chess

You can install the required dependencies using pip:
```bash
pip install chess pillow pyyaml
```

## Usage

1. **Running the Game**: To start the game, execute the main script.

python main.py

2. **Add Engines**: To add a chess engine, click the "Add Engines" button. Choose the engine's UCI executable and provide a name for it. The engine will be saved and available for selection.

3. **Start the Game**: After selecting the engine, click the "Start Game" button to begin playing. Choose which side to play, and the selected engine will play against you.

4. **Adjust Board Size**: Use the slider to adjust the board size for better visibility or for different screen resolutions.

## Structure

- **main.py**: The main application file containing the GUI and logic for the chess game.
- **assets/**: Folder containing image assets for the chess pieces (e.g., `wP.png`, `wN.png`).
- **engines.yml**: A YAML file that stores the paths of the UCI engines you've added.

## How It Works

- **Chess Board Drawing**: The board is drawn using Tkinter's Canvas widget. The images of the pieces are loaded and displayed at their respective positions. The colors of the squares alternate based on the rank and file.
  
- **Move Handling**: When a player clicks a square, the application attempts to make a move. If it's valid, the move is executed, and the board is updated. The engine also plays after each human move, and the evaluation bar updates accordingly.

- **Evaluation Bar**: The evaluation bar reflects the current position's evaluation, with white on the top and black on the bottom. The evaluation is displayed as a score from -10 (completely lost) to 10 (completely won).

## Contributing

Feel free to fork the repository and create pull requests for any features or fixes you'd like to contribute.

## License

This project is open-source and available under the MIT License.
