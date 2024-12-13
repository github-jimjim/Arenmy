import chess
import chess.engine
import tkinter as tk
from tkinter import filedialog, simpledialog
import yaml
from PIL import Image, ImageTk
import os

def draw_board(canvas, board, piece_images, last_move=None, scale=1.0):
    canvas.delete("all")
    square_size = int(60 * scale)

    canvas_images = []  # Lokale Liste, um Bildreferenzen zu speichern

    for rank in range(8):
        for file in range(8):
            x1 = file * square_size
            y1 = (7 - rank) * square_size
            x2 = x1 + square_size
            y2 = y1 + square_size

            if last_move and chess.square(file, rank) in [last_move.from_square, last_move.to_square]:
                color = "#f6f669"
            else:
                color = "#f0d9b5" if (rank + file) % 2 == 0 else "#b58863"

            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)

            piece = board.piece_at(chess.square(file, rank))
            if piece:
                piece_image = piece_images.get(piece.symbol())
                if piece_image:
                    resized_image = piece_image.resize((square_size, square_size))
                    tk_image = ImageTk.PhotoImage(resized_image)
                    canvas.create_image(x1, y1, anchor=tk.NW, image=tk_image)
                    canvas_images.append(tk_image)

    canvas.images = canvas_images

def update_eval_bar(eval_bar, eval_value, scale=1.0):
    eval_bar.delete("all")
    bar_width = int(12.5 * scale)
    bar_height = int(400 * scale)
    eval_height = max(min(int((eval_value + 10) / 20 * bar_height), bar_height), 0)

    eval_bar.create_rectangle(0, bar_height - eval_height, bar_width, bar_height, fill="white", outline="black")
    eval_bar.create_rectangle(0, 0, bar_width, bar_height - eval_height, fill="black", outline="black")

def add_engines():
    engines_file = "engines.yml"

    if os.path.exists(engines_file):
        with open(engines_file, "r") as file:
            engines = yaml.safe_load(file) or {}
    else:
        engines = {}

    engine_path = filedialog.askopenfilename(title="Wähle eine Engine aus")
    if engine_path:
        engine_name = simpledialog.askstring("Engine Name", "Gib einen Namen für die Engine ein:")
        if engine_name:
            engines[engine_name] = engine_path
            with open(engines_file, "w") as file:
                yaml.safe_dump(engines, file)

def ensure_engines():
    engines_file = "engines.yml"
    if not os.path.exists(engines_file):
        with open(engines_file, "w") as file:
            yaml.safe_dump({}, file)

    with open(engines_file, "r") as file:
        engines = yaml.safe_load(file) or {}

    if not engines:
        tk.messagebox.showinfo("Keine Engines gefunden", "Bitte füge mindestens eine Engine hinzu.")
        add_engines()

def main():
    root = tk.Tk()
    root.title("Schachbrett mit UCI-Engine")

    ensure_engines()

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    max_scale = min(screen_width / 480, screen_height / 480)
    scale = 1.0 

    canvas = tk.Canvas(root, width=int(480 * scale), height=int(480 * scale))
    canvas.grid(row=1, column=0)

    eval_bar = tk.Canvas(root, width=int(12.5 * scale), height=int(400 * scale), bg="gray")
    eval_bar.grid(row=1, column=1)

    piece_images = {}
    asset_folder = "assets"
    piece_files = {
        "P": "wP.png", "N": "wN.png", "B": "wB.png", "R": "wR.png", "Q": "wQ.png", "K": "wK.png",
        "p": "bP.png", "n": "bN.png", "b": "bB.png", "r": "bR.png", "q": "bQ.png", "k": "bK.png",
    }

    for piece, file in piece_files.items():
        file_path = os.path.join(asset_folder, file)
        if os.path.exists(file_path):
            piece_images[piece] = Image.open(file_path)

    selected_square = None
    last_move = None

    engine_var = tk.StringVar(value="Keine Engine")
    eval_engine_var = tk.StringVar(value="Keine Bewertungs-Engine")

    engines_file = "engines.yml"
    with open(engines_file, "r") as file:
        engines = yaml.safe_load(file) or {}

    engine_menu = tk.OptionMenu(root, engine_var, *engines.keys())
    engine_menu.grid(row=2, column=0)

    eval_engine_menu = tk.OptionMenu(root, eval_engine_var, *engines.keys())
    eval_engine_menu.grid(row=2, column=1)

    def start_game():
        engine_name = engine_var.get()
        eval_engine_name = eval_engine_var.get()

        if engine_name not in engines or eval_engine_name not in engines:
            print("Ungültige Engine-Auswahl")
            return

        engine_path = engines[engine_name]
        eval_engine_path = engines[eval_engine_name]

        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        eval_engine = chess.engine.SimpleEngine.popen_uci(eval_engine_path)

        board = chess.Board()

        def on_click(event):
            nonlocal selected_square, last_move
            file = event.x // int(60 * scale)
            rank = 7 - (event.y // int(60 * scale))
            clicked_square = chess.square(file, rank)

            if selected_square is None:
                if board.piece_at(clicked_square) and board.color_at(clicked_square) == board.turn:
                    selected_square = clicked_square
            else:
                move = chess.Move(selected_square, clicked_square)
                if move in board.legal_moves:
                    board.push(move)
                    last_move = move
                    draw_board(canvas, board, piece_images, last_move, scale)
                    update_evaluation()
                    root.after(100, make_engine_move)
                selected_square = None

        def make_engine_move():
            nonlocal last_move
            if not board.is_game_over():
                result = engine.play(board, chess.engine.Limit(time=1.0))
                board.push(result.move)
                last_move = result.move
                draw_board(canvas, board, piece_images, last_move, scale)
                update_evaluation()

        def update_evaluation():
            if not board.is_game_over():
                info = eval_engine.analyse(board, chess.engine.Limit(time=0.5))
                score = info["score"].white().score(mate_score=10000) / 100.0
                update_eval_bar(eval_bar, score, scale)

        def on_scale_change(val):
            nonlocal scale
            scale = min(float(val), max_scale)
            canvas.config(width=int(480 * scale), height=int(480 * scale))
            eval_bar.config(width=int(12.5 * scale), height=int(400 * scale))
            draw_board(canvas, board, piece_images, last_move, scale)
            update_evaluation()

        draw_board(canvas, board, piece_images, scale=scale)
        canvas.bind("<Button-1>", on_click)

        scale_slider = tk.Scale(root, from_=0.5, to=max_scale, resolution=0.1, orient=tk.HORIZONTAL, label="Größe", command=on_scale_change)
        scale_slider.set(scale)
        scale_slider.grid(row=3, column=0, columnspan=2)

        update_evaluation()

    start_button = tk.Button(root, text="Spiel Starten", command=start_game)
    start_button.grid(row=4, column=1)

    add_engines_button = tk.Button(root, text="Add Engines", command=add_engines)
    add_engines_button.grid(row=0, column=0, columnspan=2)

    root.mainloop()

if __name__ == "__main__":
    main()
