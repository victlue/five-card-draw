import random
import collections
from flask import Flask, session, jsonify, request, render_template

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY_HERE"

# "10" instead of "T"
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♠", "♥", "♦", "♣"]

RANK_VALUE = {r: i for i, r in enumerate(RANKS)}

def create_deck():
    deck = []
    for r in RANKS:
        for s in SUITS:
            deck.append(r + s)
    random.shuffle(deck)
    return deck

def evaluate_hand(cards):
    ranks_raw = [c[:-1] for c in cards]
    suits = [c[-1] for c in cards]
    rank_idxs = [RANK_VALUE[r] for r in ranks_raw]
    rank_idxs.sort(reverse=True)

    flush = (len(set(suits)) == 1)
    straight = False
    top_straight = None

    if all(rank_idxs[i] == rank_idxs[0] - i for i in range(5)):
        straight = True
        top_straight = rank_idxs[0]
    if set(rank_idxs) == {12, 0, 1, 2, 3}:
        straight = True
        top_straight = 3

    ccount = collections.Counter(rank_idxs)
    sorted_by_count = sorted(ccount.items(), key=lambda x: (x[1], x[0]), reverse=True)

    # Categories
    if flush and straight:
        return (8, top_straight)
    elif len(sorted_by_count) == 2:
        if sorted_by_count[0][1] == 4:
            four = sorted_by_count[0][0]
            kicker = sorted_by_count[1][0]
            return (7, four, kicker)
        else:
            three = sorted_by_count[0][0]
            pair = sorted_by_count[1][0]
            return (6, three, pair)
    elif flush:
        return (5,) + tuple(rank_idxs)
    elif straight:
        return (4, top_straight)
    elif sorted_by_count[0][1] == 3:
        three = sorted_by_count[0][0]
        kickers = [x[0] for x in sorted_by_count[1:]]
        return (3, three) + tuple(sorted(kickers, reverse=True))
    elif len(sorted_by_count) == 3:
        if sorted_by_count[0][1] == 2 and sorted_by_count[1][1] == 2:
            p1 = sorted_by_count[0][0]
            p2 = sorted_by_count[1][0]
            k = sorted_by_count[2][0]
            highp, lowp = max(p1, p2), min(p1, p2)
            return (2, highp, lowp, k)
        else:
            pair = sorted_by_count[0][0]
            kickers = [x[0] for x in sorted_by_count[1:]]
            return (1, pair) + tuple(sorted(kickers, reverse=True))
    else:
        return (0,) + tuple(rank_idxs)

def compare_hands(pcards, ccards):
    pval = evaluate_hand(pcards)
    cval = evaluate_hand(ccards)
    if pval > cval:
        return "player"
    elif cval > pval:
        return "computer"
    else:
        return "tie"

def init_game_state():
    session["round"] = 1
    session["ante"] = 2
    session["player_chips"] = 100
    session["computer_chips"] = 100
    session["deck"] = create_deck()
    session["player_hand"] = []
    session["computer_hand"] = []
    session["pot"] = 0
    session["phase"] = "start"
    session["message"] = "Welcome! Press 'Start New Game' to begin."

    session["first_to_act"] = "player"
    session["player_contrib"] = 0
    session["computer_contrib"] = 0
    session["first_action_pre_draw"] = None
    session["first_action_post_draw"] = None

def start_new_round():
    r = session["round"]
    if (r - 1) % 5 == 0 and r != 1:
        session["ante"] += 2

    session["deck"] = create_deck()
    session["player_hand"] = [session["deck"].pop() for _ in range(5)]
    session["computer_hand"] = [session["deck"].pop() for _ in range(5)]
    session["player_contrib"] = 0
    session["computer_contrib"] = 0
    session["pot"] = 0
    session["first_action_pre_draw"] = None
    session["first_action_post_draw"] = None

    ante = session["ante"]
    session["player_chips"] -= ante
    session["computer_chips"] -= ante
    session["player_contrib"] = ante
    session["computer_contrib"] = ante
    session["pot"] = ante * 2

    if session["first_to_act"] == "player":
        session["phase"] = "betting_pre_draw"
        session["message"] = f"Round {r}. Ante {ante}. Player acts first."
    else:
        session["phase"] = "computer_bet_pre_draw"
        session["message"] = f"Round {r}. Ante {ante}. Computer acts first."

def toggle_first_to_act():
    if session["first_to_act"] == "player":
        session["first_to_act"] = "computer"
    else:
        session["first_to_act"] = "player"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start_game", methods=["POST"])
def start_game():
    init_game_state()
    start_new_round()
    return jsonify(get_game_state())

@app.route("/next_round", methods=["POST"])
def next_round():
    if session["phase"] != "round_end":
        return jsonify({"error": "Round not over yet."})
    if session["player_chips"] <= 0 or session["computer_chips"] <= 0:
        session["message"] = "Game is over. Start a new game or Quit."
        return jsonify(get_game_state())

    session["round"] += 1
    toggle_first_to_act()
    start_new_round()
    return jsonify(get_game_state())

def needed_to_call(side):
    if side == "player":
        return session["computer_contrib"] - session["player_contrib"]
    else:
        return session["player_contrib"] - session["computer_contrib"]

def do_fold(folder):
    if folder == "player":
        session["message"] = "Player folds. Computer wins the pot."
        session["computer_chips"] += session["pot"]
    else:
        session["message"] = "Computer folds. Player wins the pot."
        session["player_chips"] += session["pot"]
    session["phase"] = "round_end"

def do_call(caller):
    to_call = needed_to_call(caller)
    if caller == "player":
        if to_call > session["player_chips"]:
            to_call = session["player_chips"]
        session["player_chips"] -= to_call
        session["player_contrib"] += to_call
        session["pot"] += to_call
        session["message"] = f"Player calls {to_call}."
    else:
        if to_call > session["computer_chips"]:
            to_call = session["computer_chips"]
        session["computer_chips"] -= to_call
        session["computer_contrib"] += to_call
        session["pot"] += to_call
        session["message"] = f"Computer calls {to_call}."

def do_bet(better, amount):
    if better == "player":
        old_contrib = session["player_contrib"]
        new_total = old_contrib + amount
        if new_total <= session["computer_contrib"]:
            return (False, "Bet must exceed the computer's contribution to raise.")
        if amount > session["player_chips"]:
            amount = session["player_chips"]
        session["player_chips"] -= amount
        session["player_contrib"] += amount
        session["pot"] += amount
        session["message"] = f"Player bets/raises total to {session['player_contrib']}."
        return (True, None)
    else:
        old_contrib = session["computer_contrib"]
        new_total = old_contrib + amount
        if new_total <= session["player_contrib"]:
            return (False, "Computer's bet/raise must exceed player's contribution.")
        if amount > session["computer_chips"]:
            amount = session["computer_chips"]
        session["computer_chips"] -= amount
        session["computer_contrib"] += amount
        session["pot"] += amount
        session["message"] = f"Computer bets/raises total to {session['computer_contrib']}."
        return (True, None)

@app.route("/player_bet", methods=["POST"])
def player_bet():
    data = request.json
    action = data.get("action")
    amt = data.get("bet_amount", 0)

    ph = session["phase"]
    if ph not in ("betting_pre_draw", "betting_post_draw"):
        return jsonify({"error": "Not in a player betting phase."})

    if ph == "betting_pre_draw":
        fa_key = "first_action_pre_draw"
    else:
        fa_key = "first_action_post_draw"

    fa = session[fa_key]

    if action == "fold":
        do_fold("player")
        return jsonify(get_game_state())

    elif action == "check":
        diff = needed_to_call("player")
        if diff > 0:
            return jsonify({"error": f"You must call or fold. Need {diff} to call."})
        if fa is None:
            session[fa_key] = "check"
        session["message"] = "Player checks."
        if ph == "betting_pre_draw":
            session["phase"] = "computer_bet_pre_draw"
        else:
            session["phase"] = "computer_bet_post_draw"
        return jsonify(get_game_state())

    elif action == "call":
        diff = needed_to_call("player")
        if diff <= 0:
            return jsonify({"error": "No bet to call."})
        do_call("player")
        if ph == "betting_pre_draw":
            session["phase"] = "draw_phase"
        else:
            resolve_showdown()
        return jsonify(get_game_state())

    elif action in ("bet", "raise"):
        success, err = do_bet("player", amt)
        if not success:
            return jsonify({"error": err})
        if fa is None:
            session[fa_key] = "bet"
        if ph == "betting_pre_draw":
            session["phase"] = "computer_bet_pre_draw"
        else:
            session["phase"] = "computer_bet_post_draw"
        return jsonify(get_game_state())

    else:
        return jsonify({"error": f"Invalid action: {action}"})

def computer_first_action():
    if random.random()<0.5:
        return ("check",0)
    else:
        bet_amount= random.randint(1, min(10, session["computer_chips"]))
        return ("bet",bet_amount)

def computer_second_action_after_check():
    if random.random()<0.5:
        return ("check",0)
    else:
        bet_amount= random.randint(1, min(10, session["computer_chips"]))
        return ("bet", bet_amount)

def computer_second_action_after_bet():
    diff= needed_to_call("computer")
    x= random.random()
    if x<0.3:
        return ("call", diff)
    elif x<0.6:
        return ("fold", 0)
    else:
        extra= random.randint(diff+1, min(diff+10, session["computer_chips"]))
        return ("raise", extra)

@app.route("/computer_bet", methods=["POST"])
def computer_bet():
    ph= session["phase"]
    if ph not in ("computer_bet_pre_draw","computer_bet_post_draw"):
        return jsonify({"error": "Not in computer betting phase."})

    if ph=="computer_bet_pre_draw":
        fa_key="first_action_pre_draw"
    else:
        fa_key="first_action_post_draw"

    fa= session[fa_key]

    if fa is None:
        (move, amt)= computer_first_action()
        if move=="check":
            diff= needed_to_call("computer")
            if diff>0:
                do_call("computer")
                if ph=="computer_bet_pre_draw":
                    session["phase"]="draw_phase"
                else:
                    resolve_showdown()
                return jsonify(get_game_state())
            session[fa_key]="check"
            session["message"]="Computer checks."
            session["phase"]= ph.replace("computer_bet_","betting_")
        else:
            success, err= do_bet("computer", amt)
            if not success:
                session["message"]= f"Computer tried to bet but failed: {err}"
                session["phase"]="round_end"
            else:
                session[fa_key]="bet"
                session["phase"]= ph.replace("computer_bet_","betting_")
        return jsonify(get_game_state())

    elif fa=="check":
        (move, amt)= computer_second_action_after_check()
        if move=="check":
            diff= needed_to_call("computer")
            if diff>0:
                do_call("computer")
                if ph=="computer_bet_pre_draw":
                    session["phase"]="draw_phase"
                else:
                    resolve_showdown()
            else:
                session["message"]="Computer checks."
                if ph=="computer_bet_pre_draw":
                    session["phase"]="draw_phase"
                else:
                    resolve_showdown()
        else:
            # bet
            success, err= do_bet("computer", amt)
            if not success:
                session["message"]= f"Computer bet error: {err}"
                session["phase"]="round_end"
            else:
                session[fa_key]="bet"
                session["phase"]= ph.replace("computer_bet_","betting_")

        return jsonify(get_game_state())

    else:
        # fa=="bet"
        (move, amt)= computer_second_action_after_bet()
        if move=="fold":
            do_fold("computer")
        elif move=="call":
            do_call("computer")
            if ph=="computer_bet_pre_draw":
                session["phase"]="draw_phase"
            else:
                resolve_showdown()
        else:
            # "raise"
            success, err= do_bet("computer", amt)
            if not success:
                # fallback => call
                do_call("computer")
                if ph=="computer_bet_pre_draw":
                    session["phase"]="draw_phase"
                else:
                    resolve_showdown()
            else:
                session["phase"]= ph.replace("computer_bet_","betting_")
        return jsonify(get_game_state())

@app.route("/player_draw", methods=["POST"])
def player_draw():
    if session["phase"]!="draw_phase":
        return jsonify({"error":"Not in draw phase."})
    data= request.json
    discarding= data.get("cards_to_discard",[])[:3]
    new_hand=[]
    for i,c in enumerate(session["player_hand"]):
        if i not in discarding:
            new_hand.append(c)
    for _ in range(len(discarding)):
        new_hand.append(session["deck"].pop())
    session["player_hand"]= new_hand
    session["message"]= f"Player discards {len(discarding)} card(s)."
    session["phase"]= "computer_draw"
    return jsonify(get_game_state())

@app.route("/computer_draw", methods=["POST"])
def computer_draw():
    if session["phase"]!="computer_draw":
        return jsonify({"error":"Not in computer draw phase."})
    comp= session["computer_hand"]
    cat= evaluate_hand(comp)[0]
    if cat<1:
        ranks= [RANK_VALUE[x[:-1]] for x in comp]
        sidx= sorted(range(5), key=lambda i: ranks[i])
        discarding= sidx[:3]
    elif cat==1:
        pair_rank= evaluate_hand(comp)[1]
        discarding=[]
        for i,xx in enumerate(comp):
            if RANK_VALUE[xx[:-1]]!= pair_rank:
                discarding.append(i)
        discarding= discarding[:3]
    else:
        discarding=[]

    new_hand=[]
    for i,cc in enumerate(comp):
        if i not in discarding:
            new_hand.append(cc)
    for _ in range(len(discarding)):
        new_hand.append(session["deck"].pop())
    session["computer_hand"]= new_hand
    session["message"]= f"Computer discards {len(discarding)} card(s)."
    session["player_contrib"]=0
    session["computer_contrib"]=0
    if session["first_to_act"]=="player":
        session["phase"]="betting_post_draw"
    else:
        session["phase"]="computer_bet_post_draw"
    session["first_action_post_draw"]= None
    return jsonify(get_game_state())

def resolve_showdown():
    winner= compare_hands(session["player_hand"], session["computer_hand"])
    if winner=="player":
        session["message"]="Showdown: Player wins the pot!"
        session["player_chips"]+= session["pot"]
    elif winner=="computer":
        session["message"]="Showdown: Computer wins the pot!"
        session["computer_chips"]+= session["pot"]
    else:
        session["message"]="Showdown: It's a tie! Splitting pot."
        half= session["pot"]//2
        session["player_chips"]+= half
        session["computer_chips"]+= (session["pot"]- half)
    session["phase"]="round_end"

def get_allowed_actions_for_player(phase):
    if phase not in ("betting_pre_draw","betting_post_draw"):
        return []
    if phase=="betting_pre_draw":
        fa= session["first_action_pre_draw"]
    else:
        fa= session["first_action_post_draw"]
    if fa is None:
        return ["check","bet"]
    elif fa=="check":
        return ["check","bet"]
    else:
        return ["call","raise","fold"]

def get_game_state():
    return {
        "round": session.get("round",1),
        "ante": session.get("ante",2),
        "player_chips": session.get("player_chips",100),
        "computer_chips": session.get("computer_chips",100),
        "player_hand": session.get("player_hand",[]),
        "computer_hand": session.get("computer_hand",[]),  # We'll hide or reveal in front-end
        "pot": session.get("pot",0),
        "phase": session.get("phase","start"),
        "message": session.get("message",""),
        "allowed_player_actions": get_allowed_actions_for_player(session.get("phase","start")),
    }

@app.route("/game_state", methods=["GET"])
def game_state():
    return jsonify(get_game_state())

if __name__=="__main__":
    app.run(debug=True)
