import chess
import chess.engine
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import yaml
from PIL import Image, ImageTk
import os
import pygame

def play_sound(sound_name):
    sound_folder = "sounds"
    sound_file = os.path.join(sound_folder, f"{sound_name}.mp3")
    if os.path.exists(sound_file):
        pygame.mixer.init()
        pygame.mixer.music.load(sound_file)
        pygame.mixer.music.play()

def draw_board(canvas, board, piece_images, last_move=None, scale=1.0):
    canvas.delete("all")
    square_size = int(60 * scale)

    canvas_images = []

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

def game_over(board):
    play_sound("game-end")
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            messagebox.showinfo("Spielende", "Du hast verloren! Schachmatt! 🫣")
        else:
            messagebox.showinfo("Spielende", "Herzlichen Glückwunsch! Du hast gewonnen! 🎉")
    elif board.is_stalemate():
        messagebox.showinfo("Spielende", "Unentschieden! Patt! 🤝")
    elif board.is_insufficient_material():
        messagebox.showinfo("Spielende", "Unentschieden! Ungenügendes Material. 😐")
    elif board.is_seventyfive_moves() or board.is_fivefold_repetition():
        messagebox.showinfo("Spielende", "Unentschieden durch Regelwerk! 😶")
    else:
        messagebox.showinfo("Spielende", "Spiel beendet! 😅")

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

def main():
    root = tk.Tk()
    root.title("Schachbrett mit UCI-Engine")

    engines_file = "engines.yml"
    if not os.path.exists(engines_file):
        with open(engines_file, "w") as file:
            yaml.safe_dump({}, file)

    with open(engines_file, "r") as file:
        engines = yaml.safe_load(file) or {}

    if not engines:
        messagebox.showinfo("Keine Engines", "Bitte füge eine Engine hinzu.")
        add_engines()
        with open(engines_file, "r") as file:
            engines = yaml.safe_load(file) or {}

    canvas = tk.Canvas(root, width=480, height=480)
    canvas.grid(row=1, column=0)
    piece_images = load_piece_images("assets")
    selected_square = None
    last_move = None

    engine_var = tk.StringVar(value="Keine Engine")
    eval_engine_var = tk.StringVar(value="Keine Bewertungs-Engine")

    engine_menu = tk.OptionMenu(root, engine_var, *engines.keys())
    engine_menu.grid(row=2, column=0)
    eval_engine_menu = tk.OptionMenu(root, eval_engine_var, *engines.keys())
    eval_engine_menu.grid(row=2, column=1)

    def start_game():
        engine_path = engines.get(engine_var.get())
        eval_engine_path = engines.get(eval_engine_var.get())

        if not engine_path or not eval_engine_path:
            messagebox.showerror("Fehler", "Ungültige Engine-Auswahl.")
            return

        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        board = chess.Board()
        play_sound("game-start")

        def on_click(event):
            nonlocal selected_square, last_move
            file = event.x // 60
            rank = 7 - (event.y // 60)
            clicked_square = chess.square(file, rank)

            if selected_square is None:
                if board.piece_at(clicked_square) and board.color_at(clicked_square) == board.turn:
                    selected_square = clicked_square
            else:
                move = chess.Move(selected_square, clicked_square)
                if move in board.legal_moves:
                    board.push(move)
                    play_sound("move-self")
                    last_move = move
                    draw_board(canvas, board, piece_images, last_move)
                    if board.is_game_over():
                        game_over(board)
                    else:
                        root.after(100, make_engine_move)
                else:
                    play_sound("illegal")
                selected_square = None

        def make_engine_move():
            nonlocal last_move
            if not board.is_game_over():
                result = engine.play(board, chess.engine.Limit(time=1.0))
                board.push(result.move)
                play_sound("move-opponent")
                last_move = result.move
                draw_board(canvas, board, piece_images, last_move)
                if board.is_game_over():
                    game_over(board)

        draw_board(canvas, board, piece_images)
        canvas.bind("<Button-1>", on_click)

    start_button = tk.Button(root, text="Spiel Starten", command=start_game)
    start_button.grid(row=3, column=0, columnspan=2)

    add_engines_button = tk.Button(root, text="Engines hinzufügen", command=add_engines)
    add_engines_button.grid(row=0, column=0, columnspan=2)

    root.mainloop()

def load_piece_images(asset_folder):
    piece_images = {}
    pieces = {
        "P": "wP.png", "N": "wN.png", "B": "wB.png", "R": "wR.png", "Q": "wQ.png", "K": "wK.png",
        "p": "bP.png", "n": "bN.png", "b": "bB.png", "r": "bR.png", "q": "bQ.png", "k": "bK.png",
    }
    for piece, filename in pieces.items():
        path = os.path.join(asset_folder, filename)
        if os.path.exists(path):
            piece_images[piece] = Image.open(path)
    return piece_images

if __name__ == "__main__":
    main()

