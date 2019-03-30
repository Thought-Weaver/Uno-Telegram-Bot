import numpy as np


THRESHOLD_PLAYERS = 10


class Player:
    def __init__(self, id, hand):
        self.hand = hand
        self.id = id

    def get_hand(self):
        return self.hand

    def get_id(self):
        return self.id

    def remove_card(self, id):
        if 0 <= id < len(self.hand) - 1:
            return self.hand.pop(id)
        return None

    def get_formatted_hand(self):
        text = "Your current hand:\n\n"
        for i in range(len(self.hand)):
            text += str(self.hand[i]) + "\n"
        return text

    def add_card(self, c):
        self.hand.append(c)


class Card:
    """
    For a typical card, we have 0-9 as values. 10 implies a Skip,
    11 implies a Reverse, and 12 implies a Draw Two. Each of these
    has an associated color: 'R', 'Y', 'G', 'B'

    If a card has a value of 13, it's Wild. If it has a value of
    14, it's a Draw Four Wild.

    """

    def __init__(self, value, color):
        self.value = value
        self.color = color

    def get_color(self):
        return self.color

    def get_value(self):
        return self.value

    def check_valid_color(self, c):
        return c in ['R', 'Y', 'G', 'B']

    def check_valid_value(self, v):
        return v > 0

    def is_wild(self):
        if self.value == 13 or self.value == 14:
            return True
        return False

    # Just for wilds.
    def set_color(self, c):
        if self.value == 13 or self.value == 14:
            if self.check_valid_color(c):
                self.color = c

    def __str__(self):
        text = self.color
        if self.value < 10:
            text += str(self.value)
        elif self.value == 10:
            text += " Skip"
        elif self.value == 11:
            text += " Reverse"
        elif self.value == 12:
            text += " Draw Two"
        elif self.value == 13:
            text += "Wild"
        elif self.value == 14:
            text += "Wild Draw Four"
        return text


class Deck:
    def __init__(self, num_players):
        self.deck = []
        self.played = []
        for i in range(0, 15):
            for c in ['R', 'Y', 'G', 'B']:
                if i < 10:
                    self.deck.append(Card(i, c))
                    self.deck.append(Card(i, c))
                elif i < 13:
                    self.deck.append(Card(i, c))
                elif i < 15:
                    self.deck.append(Card(i, ''))

        # If we have more than 10 players, add more cards in proportion.
        for i in range(0, num_players - THRESHOLD_PLAYERS):
            for i in range(0, 15):
                for c in ['R', 'Y', 'G', 'B']:
                    if i < 10:
                        self.deck.append(Card(i, c))
                        self.deck.append(Card(i, c))
                    elif i < 13:
                        self.deck.append(Card(i, c))
                    else:
                        self.deck.append(Card(i, ''))

    def reshuffle(self):
        if len(self.deck) <= 0 < len(self.played):
            self.deck = np.random.shuffle(self.played[:-1])
            self.played = self.played[-1]

    def draw_card(self):
        if len(self.deck) <= 0:
            self.reshuffle()
        return self.deck.pop()

    def draw_n_cards(self, n):
        cards = []
        for i in range(n):
            cards.append(self.draw_card())
        return cards

    def get_topmost_card(self):
        if len(self.played) > 0:
            return self.played[-1]
        return None

    def draw_hand(self):
        hand = []
        for i in range(7):
            hand.append(self.draw_card())
        return hand

    def play_card(self, c):
        if c.check_valid_color() and c.check_valid_value:
            self.played.append(c)

    def check_valid_play(self, c):
        top = self.get_topmost_card()
        if top is None:
            return True
        elif top.get_color() == c.get_color() or top.get_value() == c.get_value() or c.is_wild():
            return True
        return False


class Game:
    def __init__(self, players):
        self.turn = 0
        self.players = {}
        self.deck = Deck(len(players))
        self.waiting_for_wild = False
        self.waiting_for_wild_id = ""
        self.uno_pending = False
        self.uno_pending_id = ""
        self.dir = False
        self.reversed = False
        self.draw_fours_pending = 0
        self.draw_twos_pending = 0
        for i in range(len(players)):
            self.players[players[i]] = Player(i, self.deck.draw_hand())

    def play_initial_card(self):
        if self.deck.get_topmost_card() is None:
            self.deck.play_card(self.deck.draw_card())
        else:
            raise Exception("The starting card has already been played.")

    def check_for_win(self):
        for p in self.players.keys():
            if len(self.players.get(p, [])) <= 0 and not self.waiting_for_wild:
                return p
        return None

    def get_player_name_by_num(self, n):
        for p in self.players.keys():
            player = self.players[p]
            if player.get_id() == n:
                return p
        return ""

    def get_player_by_num(self, n):
        for p in self.players.keys():
            player = self.players[p]
            if player.get_id() == n:
                return player
        return None

    def play_card(self, id, card_id):
        player = self.players.get(id, None)

        if player is None:
            raise Exception("You don't seem to exist!")

        if player.get_id() != self.turn:
            raise Exception("It is not currently your turn!")

        card = player.remove_card(card_id)

        if card is None:
            raise Exception("You cannot remove the card with this ID.")

        if not self.deck.check_valid_play(card):
            raise Exception("This is not a valid card.")

        self.deck.play_card(card)
        if card.is_wild():
            self.waiting_for_wild = True
            self.waiting_for_wild_id = id
        if card.get_value() == 10:
            self.next_turn(2)
        if card.get_value() == 11:
            self.reversed = not self.reversed
        if card.get_value() == 12:
            self.draw_twos_pending += 1
        if card.get_value() == 13:
            self.waiting_for_wild = True
            self.waiting_for_wild_id = id
        if card.get_value() == 14:
            self.draw_fours_pending += 1

    def is_uno_pending(self):
        return self.uno_pending

    def check_uno_caller(self, id):
        if id != self.uno_pending_id:
            player = self.players[self.uno_pending_id]
            player.add_card(self.deck.draw_card())
            return False
        self.uno_pending = False
        self.uno_pending_id = ""
        return True

    def next_turn(self, step):
        if self.waiting_for_wild:
            raise Exception("Cannot go to next turn. Waiting for %s to choose a color." % self.waiting_for_wild_id)

        dir = -1 if self.reversed else 1
        self.turn = (self.turn + step * dir) % len(self.players)
        next_player = self.get_player_by_num(self.turn)

        for i in range(self.draw_twos_pending):
            for c in self.deck.draw_n_cards(2):
                next_player.add_card(c)

        if self.draw_twos_pending > 0:
            self.turn = (self.turn + dir) % len(self.players)
            self.draw_twos_pending = 0

        for i in range(self.draw_fours_pending):
            for c in self.deck.draw_n_cards(4):
                next_player.add_card(c)

        if self.draw_fours_pending > 0:
            self.turn = (self.turn + dir) % len(self.players)
            self.draw_fours_pending = 0

    def draw_and_continue(self, id):
        player = self.players.get(id, None)

        if player is None:
            raise Exception("You don't seem to exist!")

        if player.get_id() != self.turn:
            raise Exception("It is not currently your turn!")

        player.add_card(self.deck.draw_card())
        self.next_turn(1)

    def set_wild_color(self, id, c):
        if id != self.waiting_for_wild_id:
            raise Exception("You cannot set the wild color. Waiting for %s to set it." % self.waiting_for_wild_id)

        if not self.waiting_for_wild:
            raise Exception("An uncolored Wild card is not on top of the played pile.")

        card = self.deck.get_topmost_card()

        if not card.check_valid_color(c):
            raise Exception("That is not a valid color. Choose R, G, B, or Y.")

        card.set_color(c)

    def set_uno_pending(self, val):
        if val != True or val != False:
            raise Exception("Whether or not Uno is pending is a Boolean value.")

        self.uno_pending = val

    def is_wild_pending(self):
        return self.waiting_for_wild

    def list_players(self):
        text = "List of players:\n\n"
        for p in self.players.keys():
            text += p + " [*]" if self.players[p].get_id() == self.turn else "" + "\n"
        return text

    def get_player(self, id):
        return self.players.get(id, None)

    def get_state(self):
        text = "Current Turn: " + self.get_player_name_by_num(self.turn) + "\n"
        top_card = self.deck.get_topmost_card()
        if top_card is None:
            text += "Topmost Card: None"
        else:
            text += "Topmost Card: " + str(top_card)
        return text