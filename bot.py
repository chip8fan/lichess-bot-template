import berserk
import os
from dotenv import load_dotenv
import secrets
import time
import chess
import chess.polyglot
import sys
class Engine():
    def __init__(self):
        load_dotenv()
        self.key = os.environ.get("BOT_KEY")
        self.session = berserk.TokenSession(self.key)
        self.client = berserk.Client(session=self.session)
    def reverse_result(self, result: str):
        if result == "win":
            return "loss"
        elif result == "loss":
            return "win"
        elif result == "draw":
            return "draw"
    def read_opening_book(self, board: chess.Board):
        with chess.polyglot.open_reader("3000book.bin") as reader:
            try:
                return reader.find(board).move.uci()
            except IndexError:
                return None
    def get_material(self, board: chess.Board):
        pawns = len(board.pieces(chess.PAWN, chess.WHITE)) - len(board.pieces(chess.PAWN, chess.BLACK))
        knights = (len(board.pieces(chess.KNIGHT, chess.WHITE)) - len(board.pieces(chess.KNIGHT, chess.BLACK)))*3
        bishops = (len(board.pieces(chess.BISHOP, chess.WHITE)) - len(board.pieces(chess.BISHOP, chess.BLACK)))*3
        rooks = (len(board.pieces(chess.ROOK, chess.WHITE)) - len(board.pieces(chess.ROOK, chess.BLACK)))*5
        queens = (len(board.pieces(chess.QUEEN, chess.WHITE)) - len(board.pieces(chess.QUEEN, chess.BLACK)))*9
        material = pawns+knights+bishops+rooks+queens
        if board.is_game_over():
            if board.is_checkmate():
                if board.outcome().winner == chess.WHITE:
                    return 1000
                elif board.outcome().winner == chess.BLACK:
                    return -1000
            else:
                return 0
        elif board.can_claim_draw():
            return 0
        return material
    def evaluate(self, all_moves: str, fen: str, depth: int):
        if fen == "startpos":
            self.board = chess.Board()
        else:
            self.board = chess.Board(fen=fen)
        all_moves = all_moves.split(" ")
        for move in all_moves:
            if move != '':
                self.board.push_uci(move)
        book_move = self.read_opening_book(self.board)
        if book_move == None:
            if len(self.board.piece_map()) <= 7:
                tablebase_data = self.client.tablebase.standard(self.board.fen())
                tablebase_data = [move['uci'] for move in tablebase_data['moves'] if self.reverse_result(move['category']) == tablebase_data['category']]
                return [self.get_material(self.board), tablebase_data, True]
            else:
                legal_moves = [move.uci() for move in self.board.legal_moves]
                return [self.get_material(self.board), legal_moves, True]
        else:
            return [self.get_material(self.board), [book_move], True]     
num = 1
def not_empty(moves: list):
    if moves == ['']:
        return 0
    else:
        return len(moves)
def invert_color(color: str):
    if color == "white":
        return "black"
    elif color == "black":
        return "white"
load_dotenv()
key = os.environ.get("BOT_KEY")
session = berserk.TokenSession(key)
client = berserk.Client(session=session)
isMyTurn = False
fen = 'startpos'
for response in client.bots.stream_incoming_events():
    print(response)
    if response.get("type") == "challenge":
        game_id = response['challenge']['id']
        if response['challenge']['rated'] == True:
            client.bots.decline_challenge(game_id, 'rated')
            sys.exit()
        color = invert_color(response['challenge']['finalColor'])
        client.bots.accept_challenge(game_id)
        speed = response['challenge']['speed']
        try:
            time_remaining = response['challenge']['timeControl']['limit']
        except KeyError:
            time_remaining = 'unlimited'
        break
    elif response.get("type") == "gameStart":
        fen = response['game']['fen']
        game_id = response['game']['gameId']
        isMyTurn = response['game']['isMyTurn']
        color = response['game']['color']
        speed = response['game']['speed']
        try:
            time_remaining = response['game']['secondsLeft']
        except KeyError:
            time_remaining = 'unlimited'
        break
chess_engine = Engine()
count = 0
def make_move(move_list: str, time_limit: float):
    depth = 1
    start = time.perf_counter()
    while time.perf_counter()-start < time_limit and depth <= 10:
        print(f"depth={depth}")
        moves = chess_engine.evaluate(move_list, fen, depth)
        move = moves[1][secrets.randbelow(len(moves[1]))]
        depth += 1
        if abs(moves[0]) == 1000 or moves[2] == True:
            break
    client.bots.make_move(game_id, move)
if isMyTurn:
    if time_remaining != 'unlimited':
        make_move("", time_remaining/num)
    else:
        make_move("", 60*60*24)
    isMyTurn = False
elif color == "white" and fen == "startpos":
    if time_remaining != 'unlimited':
        make_move("", time_remaining/num)
    else:
        make_move("", 60*60*24)
for response in client.bots.stream_game_state(game_id):
    print(response)
    if response.get("type") == "gameState":
        if color == "black":
            if time_remaining != 'unlimited':
                try:
                    time_remaining = (response['btime'].hour*3600)+(response['btime'].minute*60)+(response['btime'].second)
                    if speed == 'correspondence':
                        time_remaining += response['btime'].day*86400
                except AttributeError:
                    time_remaining = response['btime'].total_seconds()
        elif color == "white":
            if time_remaining != 'unlimited':
                try:
                    time_remaining = (response['wtime'].hour*3600)+(response['wtime'].minute*60)+(response['wtime'].second)
                    if speed == 'correspondence':
                        time_remaining += response['wtime'].day*86400
                except AttributeError:
                    time_remaining = response['wtime'].total_seconds()
        count = not_empty(str(response['moves']).split(' '))
        bot_turn = (count%2==1 and color=="black") or (count%2==0 and color=="white")
        if bot_turn:
            if time_remaining != 'unlimited':
                make_move(response['moves'], time_remaining/num)
            else:
                make_move(response['moves'], 60*60*24)
    else:
        if response.get("initialFen") != None:
            fen = response['initialFen']
