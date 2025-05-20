import threading
import random
import time
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
rooms = {}  # room_code -> GameRoom instance
lock = threading.Lock()
ROOM_TIMEOUT = 1800  # 30 minutes

class GameRoom:
    def __init__(self, code):
        self.code = code
        self.players = {}  # user_id -> list of cards
        self.turn_order = []
        self.pile = []  # cards on table
        self.current_rank = 'A'
        self.ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        self.active = False
        self.last_used = time.time()
        self.thread = threading.Thread(target=self.run_game)

    def touch(self):
        self.last_used = time.time()

    def start(self):
        self.distribute_cards()
        self.active = True
        self.thread.start()
    #['♠' =s, '♥' = h, '♦' = d, '♣' =c]
    def distribute_cards(self):
        deck = [r + s for r in self.ranks for s in ['s', 'h', 'd', 'c']]
        random.shuffle(deck)
        num_players = len(self.players)
        for i, (uid, hand) in enumerate(self.players.items()):
            hand.extend(deck[i::num_players])
        self.turn_order = list(self.players.keys())

    def run_game(self):
        while self.active:
            for uid in list(self.turn_order):
                pass
            for uid, hand in self.players.items():
                if not hand:
                    self.active = False
                    return

    def play_card(self, user_id, cards):
        self.touch()
        self.pile.append((user_id, cards, self.current_rank))
        idx = self.ranks.index(self.current_rank)
        self.current_rank = self.ranks[(idx + 1) % len(self.ranks)]

    def call_bullshit(self, caller_id):
        self.touch()
        last_player, cards, claimed_rank = self.pile[-1]
        actual = all(card.startswith(claimed_rank) for card in cards)
        loser = last_player if not actual else caller_id
        for _, c, _ in self.pile:
            self.players[loser].extend(c)
        self.pile.clear()
        return loser

def cleanup_rooms():
    while True:
        time.sleep(60)
        now = time.time()
        with lock:
            to_delete = [code for code, room in rooms.items() if now - room.last_used > ROOM_TIMEOUT]
            for code in to_delete:
                del rooms[code]

cleanup_thread = threading.Thread(target=cleanup_rooms, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create', methods=['POST'])
def create_room():
    code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    with lock:
        room = GameRoom(code)
        rooms[code] = room
    return jsonify({'room_code': code})

@app.route('/join', methods=['POST'])
def join_room():
    data = request.get_json()
    code = data.get('room_code')
    uid = request.remote_addr
    with lock:
        room = rooms.get(code)
        if not room or len(room.players) >= 4:
            return jsonify({'error': 'Room full or not found'}), 404
        room.players[uid] = []
        room.touch()
        if len(room.players) >= 2 and not room.active:
            room.start()
    return jsonify({'joined': True})

@app.route('/rooms/<code>/play', methods=['POST'])
def play(code):
    data = request.get_json()
    uid = request.remote_addr
    cards = data.get('cards', [])
    room = rooms.get(code)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    room.play_card(uid, cards)
    return jsonify({'status': 'played', 'next_rank': room.current_rank})

@app.route('/rooms/<code>/bullshit', methods=['POST'])
def bullshit(code):
    uid = request.remote_addr
    room = rooms.get(code)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    loser = room.call_bullshit(uid)
    return jsonify({'loser': loser})

if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=5000)
