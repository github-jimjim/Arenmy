import os
import sys, json, time, itertools, re, concurrent.futures
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, 
                             QFormLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QComboBox, QFileDialog, 
                             QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QListWidgetItem, 
                             QAbstractItemView, QSpinBox, QInputDialog, QGroupBox)
from PyQt5.QtCore import QProcess, QThread, pyqtSignal, Qt
import chess, chess.pgn

def getConfigPath():
    return os.path.join(os.getenv("APPDATA"), "Jomfish", "config.json")

def ensureConfigDir():
    path_engine = getConfigPath()
    d = os.path.dirname(path_engine)
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(path_engine):
        fixed_engine_path = os.path.join(os.getcwd(), "jomfish_none.exe")
        engine_list = [{"name": "Jomfish 10", "command": fixed_engine_path, "protocol": "uci", 
                        "workingDirectory": os.path.dirname(fixed_engine_path), "initStrings": []}]
        with open(path_engine, "w") as f:
            json.dump(engine_list, f, indent=4)
    return path_engine

class UCIEngineParser:
    def __init__(self, command, working_dir=""):
        self.command = command
        self.working_dir = working_dir
        self.process = QProcess()
        if working_dir:
            self.process.setWorkingDirectory(working_dir)
        self.options = []
        self.buffer = ""
    def load_options(self, timeout=5000):
        self.process.start(self.command)
        if not self.process.waitForStarted(timeout):
            raise Exception("Engine could not be started.")
        self.sendCommand("uci")
        start_time = time.time()
        while True:
            if self.process.waitForReadyRead(100):
                data = self.process.readAllStandardOutput().data().decode()
                self.buffer += data
                for line in self.buffer.splitlines():
                    if line.startswith("option"):
                        self.parse_option_line(line)
                    if line.strip() == "uciok":
                        self.process.kill()
                        return self.options
            if (time.time()-start_time)*1000 > timeout:
                self.process.kill()
                break
        return self.options
    def sendCommand(self, cmd):
        self.process.write((cmd+"\n").encode())
    def parse_option_line(self, line):
        pattern = r"option name (?P<name>.+?) type (?P<type>\S+)( default (?P<default>\S+))?( min (?P<min>\S+))?( max (?P<max>\S+))?"
        m = re.search(pattern, line)
        if m:
            opt = {"name": m.group("name").strip(), "type": m.group("type").strip(),
                   "default": m.group("default") if m.group("default") is not None else "",
                   "min": m.group("min") if m.group("min") is not None else "",
                   "max": m.group("max") if m.group("max") is not None else "",
                   "value": m.group("default") if m.group("default") is not None else ""}
            if not any(o["name"] == opt["name"] for o in self.options):
                self.options.append(opt)

class UCIEngine:
    def __init__(self, command, working_dir="", use_wtime=False, time_left=1000, inc=0, color=chess.WHITE):
        self.command = command
        self.working_dir = working_dir
        self.use_wtime = use_wtime
        self.time_left = time_left
        self.inc = inc
        self.color = color
        self.process = QProcess()
        if working_dir:
            self.process.setWorkingDirectory(working_dir)
        self.buffer = ""
        self.startEngine()
    def startEngine(self):
        self.process.start(self.command)
        self.sendCommand("uci")
        self.sendCommand("isready")
    def sendCommand(self, cmd):
        if self.process.state() == QProcess.Running:
            self.process.write((cmd+"\n").encode())
    def waitForBestmove(self, max_time_ms):
        if self.use_wtime:
            if self.color == chess.WHITE:
                self.sendCommand(f"go wtime {int(self.time_left*1000)} winc {int(self.inc*1000)}")
            else:
                self.sendCommand(f"go btime {int(self.time_left*1000)} binc {int(self.inc*1000)}")
        else:
            self.sendCommand(f"go movetime {max_time_ms}")
        buffer = ""
        timeout = time.time() + (max_time_ms/1000.0 + 2)
        bestmove = None
        info_details = None
        while time.time() < timeout:
            if self.process.waitForReadyRead(100):
                data = self.process.readAllStandardOutput().data().decode()
                buffer += data
                m = re.search(r"bestmove\s+(\S+)", buffer)
                if m:
                    bestmove = m.group(1)
                    info_dict = {}
                    for line in buffer.splitlines():
                        if line.startswith("info"):
                            tokens = line.split()
                            i = 0
                            while i < len(tokens):
                                if tokens[i] == "depth" and i+1 < len(tokens):
                                    info_dict["Depth"] = tokens[i+1]
                                    i += 2
                                elif tokens[i] == "seldepth" and i+1 < len(tokens):
                                    info_dict["Seldepth"] = tokens[i+1]
                                    i += 2
                                elif tokens[i] == "multipv" and i+1 < len(tokens):
                                    info_dict["MultiPV"] = tokens[i+1]
                                    i += 2
                                elif tokens[i] == "score" and i+2 < len(tokens):
                                    info_dict["Score"] = tokens[i+2] + " " + tokens[i+1]
                                    i += 3
                                elif tokens[i] == "nodes" and i+1 < len(tokens):
                                    info_dict["Nodes"] = tokens[i+1]
                                    i += 2
                                elif tokens[i] == "nps" and i+1 < len(tokens):
                                    info_dict["NPS"] = tokens[i+1]
                                    i += 2
                                elif tokens[i] == "tbhits" and i+1 < len(tokens):
                                    info_dict["TBHits"] = tokens[i+1]
                                    i += 2
                                elif tokens[i] == "time" and i+1 < len(tokens):
                                    info_dict["Time"] = tokens[i+1] + "ms"
                                    i += 2
                                else:
                                    i += 1
                    order = ["Depth", "Seldepth", "MultiPV", "Score", "Nodes", "NPS", "TBHits", "Time"]
                    parts = [f"{key}: {info_dict[key]}" for key in order if key in info_dict]
                    info_details = " | ".join(parts)
                    break
        return bestmove, info_details, buffer
    def quit(self):
        self.sendCommand("quit")
        self.process.terminate()
        self.process.waitForFinished(3000)

class EngineConfigTab(QWidget):
    def __init__(self):
        super().__init__()
        self.options = []
        self.initUI()
    def initUI(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.engineNameEdit = QLineEdit()
        form_layout.addRow("Engine Name:", self.engineNameEdit)
        h_command = QHBoxLayout()
        self.commandEdit = QLineEdit()
        self.commandEdit.setReadOnly(True)
        self.browseButton = QPushButton("Select Engine")
        self.browseButton.clicked.connect(self.browseEngine)
        h_command.addWidget(self.commandEdit)
        h_command.addWidget(self.browseButton)
        form_layout.addRow("Engine Command:", h_command)
        self.protocolCombo = QComboBox()
        self.protocolCombo.addItems(["uci"])
        form_layout.addRow("Protocol:", self.protocolCombo)
        self.workingDirEdit = QLineEdit()
        form_layout.addRow("Working Directory:", self.workingDirEdit)
        layout.addLayout(form_layout)
        btn_layout = QHBoxLayout()
        self.loadOptionsButton = QPushButton("Load UCI Options")
        self.loadOptionsButton.clicked.connect(self.loadUCIOptions)
        self.loadSavedButton = QPushButton("Load Saved Engine")
        self.loadSavedButton.clicked.connect(self.loadSavedEngine)
        self.removeEngineButton = QPushButton("Remove Engine")
        self.removeEngineButton.clicked.connect(self.removeEngine)
        btn_layout.addWidget(self.loadOptionsButton)
        btn_layout.addWidget(self.loadSavedButton)
        btn_layout.addWidget(self.removeEngineButton)
        layout.addLayout(btn_layout)
        self.optionsTable = QTableWidget(0,5)
        self.optionsTable.setHorizontalHeaderLabels(["Name", "Type", "Default", "Min/Max", "Value"])
        header = self.optionsTable.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.optionsTable)
        self.addButton = QPushButton("Configure and Save Engine")
        self.addButton.clicked.connect(self.addEngine)
        layout.addWidget(self.addButton)
        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; font-size: 12pt; }
            QPushButton { background-color: #5A9; color: white; border-radius: 4px; padding: 8px 12px; }
            QPushButton:hover { background-color: #7CB; }
            QLineEdit, QComboBox, QTextEdit, QTableWidget { background-color: #FFF; border: 1px solid #CCC; border-radius: 4px; padding: 4px; }
            QGroupBox { font-weight: bold; border: 1px solid #AAA; border-radius: 4px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
        """)
    def browseEngine(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Engine", "", "Executable Files (*)")
        if path:
            self.commandEdit.setText(path)
            self.workingDirEdit.setText(os.path.dirname(path))
    def loadUCIOptions(self):
        cmd = self.commandEdit.text().strip()
        if not cmd:
            QMessageBox.warning(self, "Error", "Please select an engine first!")
            return
        working_dir = self.workingDirEdit.text().strip()
        parser = UCIEngineParser(cmd, working_dir)
        try:
            self.options = parser.load_options()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading options: {str(e)}")
            return
        self.populateOptionsTable()
    def populateOptionsTable(self):
        self.optionsTable.setRowCount(0)
        for opt in self.options:
            row = self.optionsTable.rowCount()
            self.optionsTable.insertRow(row)
            self.optionsTable.setItem(row, 0, QTableWidgetItem(opt["name"]))
            self.optionsTable.setItem(row, 1, QTableWidgetItem(opt["type"]))
            self.optionsTable.setItem(row, 2, QTableWidgetItem(opt["default"]))
            minmax = f"{opt['min']}/{opt['max']}" if opt["min"] and opt["max"] else ""
            self.optionsTable.setItem(row, 3, QTableWidgetItem(minmax))
            self.optionsTable.setItem(row, 4, QTableWidgetItem(opt["default"]))
    def getInitStrings(self):
        init_strings = []
        for row in range(self.optionsTable.rowCount()):
            name = self.optionsTable.item(row, 0).text()
            value = self.optionsTable.item(row, 4).text().strip()
            if value:
                init_strings.append(f"setoption name {name} value {value}")
        return init_strings
    def addEngine(self):
        if not self.engineNameEdit.text() or not self.commandEdit.text():
            QMessageBox.warning(self, "Error", "Please specify both engine name and command!")
            return
        engine = {"name": self.engineNameEdit.text(), "command": self.commandEdit.text(), 
                  "protocol": self.protocolCombo.currentText(), "workingDirectory": self.workingDirEdit.text(), 
                  "initStrings": self.getInitStrings()}
        path = ensureConfigDir()
        engines = []
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    engines = json.load(f)
            except Exception:
                engines = []
        engines = [e for e in engines if e.get("name") != engine["name"]]
        engines.append(engine)
        with open(path, "w") as f:
            json.dump(engines, f, indent=4)
        QMessageBox.information(self, "Success", f"Engine '{engine['name']}' has been configured and saved!")
    def loadSavedEngine(self):
        path = ensureConfigDir()
        if not os.path.exists(path):
            QMessageBox.information(self, "Info", "No saved engines found.")
            return
        try:
            with open(path, "r") as f:
                engines = json.load(f)
        except Exception:
            QMessageBox.warning(self, "Error", "Error loading saved engines.")
            return
        items = [e["name"] for e in engines]
        if not items:
            QMessageBox.information(self, "Info", "No saved engines found.")
            return
        item, ok = QInputDialog.getItem(self, "Load Saved Engine", "Select Engine:", items, 0, False)
        if ok and item:
            for e in engines:
                if e["name"] == item:
                    self.engineNameEdit.setText(e["name"])
                    self.commandEdit.setText(e["command"])
                    self.protocolCombo.setCurrentText(e["protocol"])
                    self.workingDirEdit.setText(e["workingDirectory"])
                    self.optionsTable.setRowCount(0)
                    if "initStrings" in e and e["initStrings"]:
                        for init in e["initStrings"]:
                            parts = init.split(" value ")
                            if len(parts) == 2:
                                opt_name = parts[0].replace("setoption name ", "").strip()
                                opt_value = parts[1].strip()
                                row = self.optionsTable.rowCount()
                                self.optionsTable.insertRow(row)
                                self.optionsTable.setItem(row, 0, QTableWidgetItem(opt_name))
                                self.optionsTable.setItem(row, 1, QTableWidgetItem(""))
                                self.optionsTable.setItem(row, 2, QTableWidgetItem(""))
                                self.optionsTable.setItem(row, 3, QTableWidgetItem(""))
                                self.optionsTable.setItem(row, 4, QTableWidgetItem(opt_value))
                    return
    def removeEngine(self):
        path = ensureConfigDir()
        if not os.path.exists(path):
            QMessageBox.information(self, "Info", "No saved engines found.")
            return
        try:
            with open(path, "r") as f:
                engines = json.load(f)
        except Exception:
            QMessageBox.warning(self, "Error", "Error loading saved engines.")
            return
        items = [e["name"] for e in engines]
        if not items:
            QMessageBox.information(self, "Info", "No saved engines found.")
            return
        item, ok = QInputDialog.getItem(self, "Remove Engine", "Select Engine to remove:", items, 0, False)
        if ok and item:
            engines = [e for e in engines if e["name"] != item]
            with open(path, "w") as f:
                json.dump(engines, f, indent=4)
            QMessageBox.information(self, "Success", f"Engine '{item}' has been removed!")
            self.engineNameEdit.clear()
            self.commandEdit.clear()
            self.workingDirEdit.clear()
            self.optionsTable.setRowCount(0)

class TournamentThread(QThread):
    tournamentLog = pyqtSignal(str)
    tournamentBoard = pyqtSignal(str)
    tournamentEngineInfoWhite = pyqtSignal(str)
    tournamentEngineInfoBlack = pyqtSignal(str)
    tournamentEngineRaw = pyqtSignal(str)
    tournamentPGN = pyqtSignal(str)
    tournamentFinished = pyqtSignal(str)
    def __init__(self, engines, movetime, rounds, concurrency, use_movetime=True):
        super().__init__()
        self.engines = engines
        self.movetime = movetime
        self.rounds = rounds
        self.concurrency = concurrency
        self.use_movetime = use_movetime
    def run(self):
        overall_log = ""
        results = {}
        pgn_games = []
        games = []
        for _ in range(self.rounds):
            pairs = list(itertools.combinations(self.engines, 2))
            for pair in pairs:
                games.append((pair[0], pair[1]))
                games.append((pair[1], pair[0]))
        total_games = len(games)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_game = {executor.submit(self.simulate_game, white, black): (white, black) for white, black in games}
            game_index = 0
            for future in concurrent.futures.as_completed(future_to_game):
                white, black = future_to_game[future]
                try:
                    game_log, result, pgn_text = future.result()
                except Exception:
                    game_log, result, pgn_text = "Error during simulation.", "Abort", ""
                game_index += 1
                overall_log += f"Game {game_index}/{total_games}: {white['name']} (White) vs. {black['name']} (Black)\n"
                overall_log += game_log + "\nResult: " + result + "\n\n"
                pgn_games.append(pgn_text)
                results.setdefault(white['name'], 0)
                results.setdefault(black['name'], 0)
                if result=="1-0":
                    results[white['name']] += 1
                elif result=="0-1":
                    results[black['name']] += 1
                else:
                    results[white['name']] += 0.5
                    results[black['name']] += 0.5
                self.tournamentLog.emit(overall_log)
        summary = "Tournament finished. Results:\n"
        for name, score in results.items():
            summary += f"{name}: {score} points\n"
        pgn_combined = "\n\n".join(pgn_games)
        self.tournamentPGN.emit(pgn_combined)
        self.tournamentFinished.emit(summary)
    def simulate_game(self, white_config, black_config):
        board = chess.Board()
        game = chess.pgn.Game()
        game.headers["White"] = white_config["name"]
        game.headers["Black"] = black_config["name"]
        node = game
        game_log = ""
        move_count = 0
        white_engine = UCIEngine(white_config["command"], white_config.get("workingDirectory", ""), False, 0, 0, color=chess.WHITE)
        black_engine = UCIEngine(black_config["command"], black_config.get("workingDirectory", ""), False, 0, 0, color=chess.BLACK)
        for cmd in white_config.get("initStrings", []):
            white_engine.sendCommand(cmd)
        for cmd in black_config.get("initStrings", []):
            black_engine.sendCommand(cmd)
        time.sleep(1)
        while not board.is_game_over() and move_count < 200:
            current_color = board.turn
            current_engine = white_engine if current_color==chess.WHITE else black_engine
            available_time_ms = int(self.movetime * 1000)
            current_engine.sendCommand("position fen " + board.fen())
            bestmove, info_details, raw_output = current_engine.waitForBestmove(available_time_ms)
            prefix = "White" if current_color==chess.WHITE else "Black"
            self.tournamentEngineRaw.emit(f"{prefix} raw: {raw_output}")
            if not bestmove:
                game_log += "No answer from engine.\n"
                result = "Abort"
                break
            try:
                move = chess.Move.from_uci(bestmove)
            except Exception:
                game_log += f"Invalid move: {bestmove}\n"
                result = "Abort"
                break
            if move not in board.legal_moves:
                game_log += f"Illegal move: {bestmove}\n"
                result = "Abort"
                break
            board.push(move)
            node = node.add_variation(move)
            move_count += 1
            board_state = board.unicode(borders=True)
            white_debug = f"White {white_config['name']}: {info_details if info_details else 'idle'}"
            black_debug = f"Black {black_config['name']}: {info_details if info_details else 'idle'}"
            self.tournamentEngineInfoWhite.emit(white_debug)
            self.tournamentEngineInfoBlack.emit(black_debug)
            self.tournamentBoard.emit(f"{board_state}\nActive: {'White' if board.turn==chess.WHITE else 'Black'} - {white_config['name'] if board.turn==chess.BLACK else black_config['name']}")
            game_log += f"{move_count}. {'White' if board.turn==chess.BLACK else 'Black'} plays {move.uci()} (movetime {self.movetime}s)\n"
        result = board.result() if board.is_game_over() else "Abort"
        white_engine.quit()
        black_engine.quit()
        pgn_text = str(game)
        return game_log, result, pgn_text

class TournamentTab(QWidget):
    def __init__(self):
        super().__init__()
        self.engines = []
        self.thread = None
        self.initUI()
        self.loadEngineList()
    def initUI(self):
        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        self.engineListWidget = QListWidget()
        self.engineListWidget.setSelectionMode(QAbstractItemView.MultiSelection)
        top_layout.addWidget(QLabel("Available Engines:"))
        top_layout.addWidget(self.engineListWidget)
        self.refreshButton = QPushButton("Refresh")
        self.refreshButton.clicked.connect(self.loadEngineList)
        top_layout.addWidget(self.refreshButton)
        main_layout.addLayout(top_layout)
        debug_layout = QHBoxLayout()
        self.tournamentLog = QTextEdit()
        self.tournamentLog.setReadOnly(True)
        self.engineRawDebug = QTextEdit()
        self.engineRawDebug.setReadOnly(True)
        debug_layout.addWidget(QLabel("Tournament Log:"))
        debug_layout.addWidget(QLabel("Engine Raw Debug:"))
        logs_layout = QHBoxLayout()
        logs_layout.addWidget(self.tournamentLog)
        logs_layout.addWidget(self.engineRawDebug)
        main_layout.addLayout(logs_layout)
        self.boardArea = QTextEdit()
        self.boardArea.setReadOnly(True)
        main_layout.addWidget(QLabel("Board (ASCII, Live):"))
        main_layout.addWidget(self.boardArea)
        hlayout_debug = QHBoxLayout()
        self.debugWhite = QLineEdit()
        self.debugWhite.setReadOnly(True)
        self.debugWhite.setPlaceholderText("Summarized Debug White")
        self.debugBlack = QLineEdit()
        self.debugBlack.setReadOnly(True)
        self.debugBlack.setPlaceholderText("Summarized Debug Black")
        hlayout_debug.addWidget(self.debugWhite)
        hlayout_debug.addWidget(self.debugBlack)
        main_layout.addWidget(QLabel("Summarized Engine Debug:"))
        main_layout.addLayout(hlayout_debug)
        tc_layout = QFormLayout()
        self.movetimeEdit = QLineEdit("1")
        self.roundsSpin = QSpinBox()
        self.roundsSpin.setMinimum(1)
        self.roundsSpin.setValue(1)
        self.concurrencySpin = QSpinBox()
        self.concurrencySpin.setMinimum(1)
        self.concurrencySpin.setValue(1)
        tc_layout.addRow("Time per move (s):", self.movetimeEdit)
        tc_layout.addRow("Rounds (Round Robin):", self.roundsSpin)
        tc_layout.addRow("Concurrency:", self.concurrencySpin)
        main_layout.addLayout(tc_layout)
        self.startTournamentButton = QPushButton("Start Tournament")
        self.startTournamentButton.clicked.connect(self.startTournament)
        main_layout.addWidget(self.startTournamentButton)
        self.savePGNButton = QPushButton("Save PGN")
        self.savePGNButton.clicked.connect(self.savePGN)
        main_layout.addWidget(self.savePGNButton)
        self.setLayout(main_layout)
        self.setStyleSheet("""
            QWidget { font-family: 'Segoe UI'; font-size: 11pt; }
            QPushButton { background-color: #008CBA; color: white; border-radius: 4px; padding: 6px 10px; }
            QPushButton:hover { background-color: #00A0DC; }
            QLineEdit, QComboBox, QTextEdit, QTableWidget, QListWidget { background-color: #FFF; border: 1px solid #DDD; border-radius: 4px; padding: 4px; }
            QLabel { color: #333; }
            QGroupBox { font-weight: bold; border: 1px solid #AAA; border-radius: 4px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        """)
    def loadEngineList(self):
        path = getConfigPath()
        self.engines = []
        self.engineListWidget.clear()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self.engines = json.load(f)
            except Exception:
                QMessageBox.warning(self, "Error", "Error loading engines.json")
        else:
            QMessageBox.information(self, "Info", "No engines.json found.")
        for engine in self.engines:
            item = QListWidgetItem(engine.get("name", "Unknown"))
            self.engineListWidget.addItem(item)
    def startTournament(self):
        selected_items = self.engineListWidget.selectedItems()
        if len(selected_items) < 2:
            QMessageBox.warning(self, "Error", "Please select at least two engines!")
            return
        selected_engines = [e for e in self.engines if e.get("name") in [item.text() for item in selected_items]]
        try:
            movetime = float(self.movetimeEdit.text().strip())
            rounds = self.roundsSpin.value()
            concurrency = self.concurrencySpin.value()
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid time-control values!")
            return
        self.tournamentLog.clear()
        self.engineRawDebug.clear()
        self.thread = TournamentThread(selected_engines, movetime, rounds, concurrency, use_movetime=True)
        self.thread.tournamentLog.connect(self.appendTournamentLog)
        self.thread.tournamentBoard.connect(self.updateBoard)
        self.thread.tournamentEngineInfoWhite.connect(self.updateSummarizedWhite)
        self.thread.tournamentEngineInfoBlack.connect(self.updateSummarizedBlack)
        self.thread.tournamentEngineRaw.connect(self.appendEngineRaw)
        self.thread.tournamentPGN.connect(self.saveTournamentPGN)
        self.thread.tournamentFinished.connect(self.appendTournamentLog)
        self.thread.start()
    def appendTournamentLog(self, text):
        self.tournamentLog.setPlainText(text)
        self.tournamentLog.verticalScrollBar().setValue(self.tournamentLog.verticalScrollBar().maximum())
    def appendEngineRaw(self, text):
        self.engineRawDebug.append(text)
        self.engineRawDebug.verticalScrollBar().setValue(self.engineRawDebug.verticalScrollBar().maximum())
    def updateBoard(self, board_text):
        self.boardArea.setPlainText(board_text)
    def updateSummarizedWhite(self, text):
        self.debugWhite.setText(text)
    def updateSummarizedBlack(self, text):
        self.debugBlack.setText(text)
    def saveTournamentPGN(self, pgn_text):
        self.tournamentPGN = pgn_text
    def savePGN(self):
        if hasattr(self, "tournamentPGN") and self.tournamentPGN.strip():
            path, _ = QFileDialog.getSaveFileName(self, "Save PGN", "", "PGN Files (*.pgn)")
            if path:
                with open(path, "w") as f:
                    f.write(self.tournamentPGN)
                QMessageBox.information(self, "Success", "PGN saved!")
        else:
            QMessageBox.warning(self, "Error", "No PGN data available.")

class PlayGameTab(QWidget):
    def __init__(self):
        super().__init__()
        self.board = chess.Board()
        self.engine = None
        self.game = chess.pgn.Game()
        self.node = self.game
        self.engineName = ""
        self.engines = []
        self.initUI()
        self.loadEngines()
    def initUI(self):
        main_layout = QVBoxLayout()
        header_layout = QHBoxLayout()
        self.playerLabel = QLabel("Human (White)")
        self.engineLabel = QLabel("Engine: [not selected] (Black)")
        header_layout.addWidget(self.playerLabel)
        header_layout.addWidget(self.engineLabel)
        main_layout.addLayout(header_layout)
        board_group = QGroupBox("Live Board")
        board_layout = QVBoxLayout()
        self.boardArea = QTextEdit()
        self.boardArea.setReadOnly(True)
        board_layout.addWidget(self.boardArea)
        board_group.setLayout(board_layout)
        main_layout.addWidget(board_group)
        control_layout = QHBoxLayout()
        self.moveInput = QLineEdit()
        self.moveInput.setPlaceholderText("Your move (e.g. e2e4)")
        self.moveButton = QPushButton("Send Move")
        self.moveButton.clicked.connect(self.humanMove)
        control_layout.addWidget(self.moveInput)
        control_layout.addWidget(self.moveButton)
        main_layout.addLayout(control_layout)
        self.gameLog = QTextEdit()
        self.gameLog.setReadOnly(True)
        main_layout.addWidget(QLabel("Game Log:"))
        main_layout.addWidget(self.gameLog)
        debug_group = QGroupBox("Engine Debug Info")
        debug_layout = QHBoxLayout()
        self.engineDebug = QLineEdit()
        self.engineDebug.setReadOnly(True)
        self.engineDebug.setPlaceholderText("Engine debug info will appear here...")
        debug_layout.addWidget(self.engineDebug)
        debug_group.setLayout(debug_layout)
        main_layout.addWidget(debug_group)
        top_layout = QHBoxLayout()
        self.selectEngineButton = QPushButton("Select Engine")
        self.selectEngineButton.clicked.connect(self.selectEngine)
        self.refreshEnginesButton = QPushButton("Refresh")
        self.refreshEnginesButton.clicked.connect(self.loadEngines)
        top_layout.addWidget(self.selectEngineButton)
        top_layout.addWidget(self.refreshEnginesButton)
        main_layout.addLayout(top_layout)
        self.savePGNButton = QPushButton("Save PGN")
        self.savePGNButton.clicked.connect(self.savePGN)
        main_layout.addWidget(self.savePGNButton)
        self.setLayout(main_layout)
        self.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid #888; border-radius: 4px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QPushButton { background-color: #E91E63; color: white; border-radius: 4px; padding: 6px 10px; }
            QPushButton:hover { background-color: #EC407A; }
            QLineEdit, QTextEdit, QComboBox { background-color: #FFF; border: 1px solid #CCC; border-radius: 4px; padding: 4px; }
            QLabel { color: #333; }
        """)
        self.updateBoardDisplay()
    def loadEngines(self):
        path = getConfigPath()
        self.engines = []
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    self.engines = json.load(f)
            except Exception:
                QMessageBox.warning(self, "Error", "Error loading engines.json")
        else:
            QMessageBox.information(self, "Info", "No engines.json found.")
    def updateBoardDisplay(self):
        state = self.board.unicode(borders=True)
        self.boardArea.setPlainText(state + f"\n\nWhite: Human | Black: {self.engineName if self.engineName else '[not selected]'}")
    def selectEngine(self):
        self.loadEngines()
        if not self.engines:
            QMessageBox.information(self, "Info", "No engines available!")
            return
        items = [e["name"] for e in self.engines]
        item, ok = QInputDialog.getItem(self, "Select Engine", "Available Engines:", items, 0, False)
        if ok and item:
            for e in self.engines:
                if e["name"] == item:
                    self.engineName = e["name"]
                    self.engineLabel.setText(f"Engine: {self.engineName} (Black)")
                    self.engine = UCIEngine(e["command"], e.get("workingDirectory", ""), False, 0, 0, color=chess.BLACK)
                    for cmd in e.get("initStrings", []):
                        self.engine.sendCommand(cmd)
                    break
    def startGame(self):
        if not self.engine:
            self.selectEngine()
            if not self.engine:
                QMessageBox.warning(self, "Error", "No engine selected!")
                return
        self.engine.sendCommand("uci")
        self.engine.sendCommand("isready")
        self.board.reset()
        self.game = chess.pgn.Game()
        self.node = self.game
        self.game.headers["White"] = "Human"
        self.game.headers["Black"] = self.engineName if self.engineName else "Engine"
        self.gameLog.append("Game started. You play as White. 1s per move.")
        self.updateBoardDisplay()
    def humanMove(self):
        if self.board.is_game_over():
            self.gameLog.append("Game over!")
            return
        move_str = self.moveInput.text().strip()
        try:
            move = self.board.parse_san(move_str)
        except Exception:
            try:
                move = chess.Move.from_uci(move_str)
            except Exception:
                QMessageBox.warning(self, "Error", "Invalid move!")
                return
        if move not in self.board.legal_moves:
            QMessageBox.warning(self, "Error", "Illegal move!")
            return
        self.board.push(move)
        self.node = self.node.add_variation(move)
        self.updateBoardDisplay()
        self.gameLog.append(f"You: {move.uci()}")
        if self.engine:
            self.engine.sendCommand("position fen " + self.board.fen())
            bestmove, info_details, _ = self.engine.waitForBestmove(1000)
            if bestmove:
                try:
                    engine_move = chess.Move.from_uci(bestmove)
                    self.board.push(engine_move)
                    self.node = self.node.add_variation(engine_move)
                    self.updateBoardDisplay()
                    self.gameLog.append(f"Engine: {engine_move.uci()}")
                    self.engineDebug.setText(info_details if info_details else "No debug info")
                except Exception:
                    self.gameLog.append("Error in engine move.")
            else:
                self.gameLog.append("No response from engine.")
        self.moveInput.clear()
    def savePGN(self):
        pgn_text = str(self.game)
        if not pgn_text.strip():
            QMessageBox.warning(self, "Error", "No PGN data available.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save PGN", "", "PGN Files (*.pgn)")
        if path:
            with open(path, "w") as f:
                f.write(pgn_text)
            QMessageBox.information(self, "Success", "PGN saved!")
            
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensureConfigDir()
        self.setWindowTitle("Custom UCI Engine Manager, Tournament & Game")
        self.resize(1200, 900)
        tabs = QTabWidget()
        tabs.addTab(EngineConfigTab(), "Engine Configuration")
        tabs.addTab(TournamentTab(), "Tournament")
        play_tab = PlayGameTab()
        play_container = QWidget()
        play_layout = QVBoxLayout()
        start_game_btn = QPushButton("Start Game vs. Engine")
        start_game_btn.clicked.connect(play_tab.startGame)
        play_layout.addWidget(start_game_btn)
        play_layout.addWidget(play_tab)
        play_container.setLayout(play_layout)
        tabs.addTab(play_container, "Game")
        self.setCentralWidget(tabs)
        self.setStyleSheet("QMainWindow { background-color: #ECEFF1; }")
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
