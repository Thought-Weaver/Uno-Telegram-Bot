# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import telegram
from telegram.error import Unauthorized, TelegramError

import random


THRESHOLD_PLAYERS = 10

with open("api_key.txt", 'r') as f:
    TOKEN = f.read().rstrip()

bot = telegram.Bot(token=TOKEN)


class Player:
    def __init__(self, id, hand):
        self.hand = hand
        self.id = id

    def get_hand(self):
        return self.hand

    def get_id(self):
        return self.id

    def remove_card(self, id):
        if 0 <= id < len(self.hand):
            return self.hand.pop(id)
        return None

    def get_formatted_hand(self):
        text = "Your current hand:\n\n"
        for i in range(len(self.hand)):
            text += "(" + str(i) + ") " + str(self.hand[i]) + "\n"
        return text

    def add_card(self, c):
        self.hand.append(c)

    def insert_card(self, c, i):
        self.hand.insert(i, c)

    def set_hand(self, hand):
        self.hand = hand


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

    def check_valid_color(self):
        return self.color in ['R', 'Y', 'G', 'B']

    def check_valid_value(self):
        return self.value >= 0

    def is_wild(self):
        if self.value == 13 or self.value == 14:
            return True
        return False

    # Just for wilds.
    def set_color(self, c):
        if self.value == 13 or self.value == 14:
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
            text += " Wild"
        elif self.value == 14:
            text += " Wild Draw Four"
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
        for i in range(0, max(0, num_players - THRESHOLD_PLAYERS)):
            for j in range(0, 15):
                for c in ['R', 'Y', 'G', 'B']:
                    if j < 10:
                        self.deck.append(Card(i, c))
                        self.deck.append(Card(i, c))
                    elif j < 13:
                        self.deck.append(Card(i, c))
                    else:
                        self.deck.append(Card(i, ''))

        random.shuffle(self.deck)

    def double_deck(self):
        if len(self.deck) <= 0 and len(self.played) <= 0:
            for i in range(0, 15):
                for c in ['R', 'Y', 'G', 'B']:
                    if i < 10:
                        self.deck.append(Card(i, c))
                        self.deck.append(Card(i, c))
                    elif i < 13:
                        self.deck.append(Card(i, c))
                    elif i < 15:
                        self.deck.append(Card(i, ''))
            random.shuffle(self.deck)

    def reshuffle(self):
        if len(self.deck) <= 0 < len(self.played):
            self.deck = random.shuffle(self.played[:-1])
            self.played = self.played[-1]

    def draw_card(self):
        if len(self.deck) <= 0 and len(self.played) <= 0:
            self.double_deck()
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
        if c.is_wild():
            self.played.append(c)
            return

        if c.check_valid_color() and c.check_valid_value():
            self.played.append(c)

    def check_valid_play(self, c):
        top = self.get_topmost_card()
        if top is None:
            return True
        if top.get_color() == c.get_color() or top.get_value() == c.get_value() or c.is_wild():
            return True
        return False

    def return_card(self, c):
        if c.check_valid_color() and c.check_valid_value():
            self.deck.insert(0, c)

    def set_wild(self, c):
        if c.lower() in ['r', 'y', 'g', 'b'] and self.get_topmost_card().is_wild():
            self.played[-1].set_color(c.upper())


class Game:
    def __init__(self, chat_id, players):
        self.turn = 0
        self.players = {}
        self.players_and_names = players
        self.players_and_ready = {}
        self.ready_to_play = False
        self.deck = Deck(len(players))

        self.waiting_for_wild = False
        self.waiting_for_wild_id = ""
        self.waiting_for_wild_name = ""
        self.uno_pending = False
        self.uno_pending_id = ""

        self.skip_pending = False
        self.dir = False
        self.reversed = False
        self.draw_fours_pending = 0
        self.draw_twos_pending = 0

        self.chat_id = chat_id
        self.hpt_lap = -1

        self.advanced_rules = False
        self.waiting_for_seven = False
        self.waiting_for_seven_id = ""
        self.waiting_for_seven_name = ""

        self.last_num_cards_drawn = 0
        count = 0
        for user_id, name in players.items():
            self.send_message(name + " has been added to the game.\n")
            self.players[user_id] = Player(count, self.deck.draw_hand())
            self.players_and_ready[user_id] = False
            count += 1
        self.send_message("Everything has been set up. Waiting for players to /ready.\n")

    def send_message(self, text):
        try:
            bot.send_message(chat_id=self.chat_id, text=text)
        except TelegramError as e:
            raise e

    def set_hpt_lap(self, lap):
        self.hpt_lap = lap

    def get_hpt_lap(self):
        return self.hpt_lap

    def get_players_and_ready(self):
        return self.players_and_ready

    def set_ready_to_play(self, val):
        if val != False and val != True:
            self.send_message("Ready to play must be a Boolean value.")
            return
        self.ready_to_play = val

    def get_ready_to_play(self):
        return self.ready_to_play

    def set_advanced_rules(self, val):
        if val != False and val != True:
            self.send_message("Advanced rules to play must be a Boolean value.")
            return
        self.advanced_rules = val

    def is_advanced_rules(self):
        return self.advanced_rules

    def play_initial_card(self):
        if self.deck.get_topmost_card() is None:
            card = self.deck.draw_card()
            while card.value >= 10:
                self.deck.return_card(card)
                card = self.deck.draw_card()
            self.deck.play_card(card)
        else:
            self.send_message("The starting card has already been played.")

    def check_for_win(self):
        for p in self.players.keys():
            if len(self.players.get(p, []).get_hand()) <= 0 and not self.waiting_for_wild:
                return p
        return None

    def get_player_id_by_num(self, n):
        for p in self.players.keys():
            player = self.players[p]
            if player.get_id() == n:
                return p
        return ""

    def get_player_name_by_num(self, n):
        for p in self.players.keys():
            player = self.players[p]
            if player.get_id() == n:
                return self.players_and_names[p]
        return ""

    def get_player_by_num(self, n):
        for p in self.players.keys():
            player = self.players[p]
            if player.get_id() == n:
                return player
        return None

    def play_zero(self):
        dir = -1 if self.reversed else 1
        last_hand = None

        if dir == 1:
            iter_range = range(len(self.players))
        else:
            iter_range = range(len(self.players) - 1, -1, -1)

        for i in iter_range:
            player = self.get_player_by_num(i)
            next_player = self.get_player_by_num((i + dir) % len(self.players))
            if last_hand is None:
                last_hand = player.get_hand()
            player.set_hand(next_player.get_hand())
            if i == len(self.players) - 1:
                player.set_hand(last_hand)

    def play_seven(self, user_id_1, user_id_2):
        player_1 = self.players.get(user_id_1)
        player_2 = self.players.get(user_id_2)

        if self.players.get(user_id_1).get_id() != self.turn:
            self.send_message("It is not currently your turn!")
            return False

        if not self.waiting_for_seven:
            self.send_message("A seven is not on top of the played pile.")
            return False

        if user_id_1 != self.waiting_for_seven_id:
            self.send_message("You cannot swap! Waiting for %s to swap." % self.waiting_for_seven_name)
            return False

        if player_1 is None:
            self.send_message("You don't seem to exist!")
            return False

        if player_2 is None:
            self.send_message("The player you chose doesn't seem to exist!")
            return False

        if user_id_1 == user_id_2:
            self.send_message("You cannot swap hands with yourself!")
            return False

        temp_hand = player_1.get_hand()
        player_1.set_hand(player_2.get_hand())
        player_2.set_hand(temp_hand)

        self.waiting_for_seven = False
        self.waiting_for_seven_id = ""
        self.waiting_for_seven_name = ""

        return True

    def play_card(self, id, card_id):
        player = self.players.get(id)

        if player is None:
            self.send_message("You don't seem to exist!")
            return False

        if player.get_id() != self.turn:
            self.send_message("It is not currently your turn!")
            return False

        if self.advanced_rules and self.waiting_for_seven:
            self.send_message("You cannot play a card; waiting for %s to choose a player for swapping hands." %
                              self.waiting_for_seven_name)
            return False

        if self.waiting_for_wild:
            self.send_message("You cannot play a card; waiting for %s to set the wild color." %
                              self.waiting_for_wild_name)
            return False

        if self.uno_pending:
            self.send_message("You cannot play a card; Uno is pending.")

        if self.waiting_for_seven:
            self.send_message("You cannot play a card; a seven is pending.")

        card = player.remove_card(card_id)

        if card is None:
            self.send_message("You cannot remove the card with this ID.")
            return False

        if not self.deck.check_valid_play(card):
            self.send_message("This is not a valid card.")
            player.insert_card(card, card_id)
            return False

        self.deck.play_card(card)
        if self.advanced_rules and card.get_value() == 0:
            self.play_zero()
            self.send_message("Everyone's hands have rotated!")
        if self.advanced_rules and card.get_value() == 7:
            self.waiting_for_seven = True
            self.waiting_for_seven_id = id
            self.waiting_for_seven_name = self.players_and_names[id]
            self.send_message("Now choose a player with whom you'll swap hands using /seven [player_num]!")
        if card.is_wild():
            self.waiting_for_wild = True
            self.waiting_for_wild_id = id
            self.waiting_for_wild_name = self.players_and_names[id]
            self.send_message("Now choose a color using /wild R, Y, G, or B!")
        if card.get_value() == 10:
            self.skip_pending = True
            return True
        if card.get_value() == 11:
            self.reversed = not self.reversed
            self.send_message("The direction of the game has been reversed!")
        if card.get_value() == 12:
            self.draw_twos_pending += 1
        if card.get_value() == 14:
            self.draw_fours_pending += 1

        return True

    def is_uno_pending(self):
        return self.uno_pending

    def is_skip_pending(self):
        return self.skip_pending

    def is_seven_pending(self):
        return self.waiting_for_seven

    def set_skip_pending(self, val):
        if val != False and val != True:
            self.send_message("Skip pending must be a Boolean value.")
            return
        self.skip_pending = val

    def check_uno_caller(self, id):
        if self.players_and_names.get(id) is None:
            self.send_message("You are not in the game!")
            return -1

        if id != self.uno_pending_id:
            self.players[self.uno_pending_id].add_card(self.deck.draw_card())
            self.uno_pending = False
            self.uno_pending_id = ""
            return 0

        self.uno_pending = False
        self.uno_pending_id = ""
        return 1

    def account_draw_twos(self):
        dir = -1 if self.reversed else 1
        next_player = self.get_player_by_num(self.turn)
        for i in range(self.draw_twos_pending):
            for c in self.deck.draw_n_cards(2):
                next_player.add_card(c)

        if self.draw_twos_pending > 0:
            self.send_message(self.get_player_name_by_num(self.turn) +
                              " has to draw %d cards!" % (self.draw_twos_pending * 2))
            self.turn = (self.turn + dir) % len(self.players)
            self.draw_twos_pending = 0

    def account_draw_fours(self):
        dir = -1 if self.reversed else 1
        next_player = self.get_player_by_num(self.turn)
        for i in range(self.draw_fours_pending):
            for c in self.deck.draw_n_cards(4):
                next_player.add_card(c)

        if self.draw_fours_pending > 0:
            self.send_message(self.get_player_name_by_num(self.turn) +
                              " has to draw %d cards!" % (self.draw_fours_pending * 4))
            self.turn = (self.turn + dir) % len(self.players)
            self.draw_fours_pending = 0

    def next_turn(self, step):
        # This has to happen before in case the last player didn't stack.
        if self.draw_twos_pending > 0 and self.deck.get_topmost_card().get_value() != 12:
            self.send_message(self.get_player_name_by_num(self.turn) + " failed to stack their draw two!")
            self.account_draw_twos()
        if self.draw_fours_pending > 0 and self.deck.get_topmost_card().get_value() != 14:
            self.send_message(self.get_player_name_by_num(self.turn) + " failed to stack their draw four!")
            self.account_draw_fours()

        dir = -1 if self.reversed else 1
        self.turn = (self.turn + step * dir) % len(self.players)
        next_player = self.get_player_by_num(self.turn)

        # This happens after in case the next player cannot stack.
        if self.draw_twos_pending > 0 and len(list(filter(lambda c: c.get_value() == 12, next_player.get_hand()))) <= 0:
            self.send_message(self.get_player_name_by_num(self.turn) + " couldn't stack a draw two!")
            self.account_draw_twos()
        if self.draw_fours_pending > 0 and len(list(filter(lambda c: c.get_value() == 14, next_player.get_hand()))) <= 0:
            self.send_message(self.get_player_name_by_num(self.turn) + " couldn't stack a draw four!")
            self.account_draw_fours()

    def draw_and_continue(self, id):
        player = self.players.get(id, None)

        if player is None:
            self.send_message("You don't seem to exist!")
            return False

        if player.get_id() != self.turn:
            self.send_message("It is not currently your turn!")
            return False

        if self.waiting_for_wild:
            self.send_message("You cannot draw a card; waiting for %s to set the wild color." %
                              self.waiting_for_wild_name)
            return

        if self.uno_pending:
            self.send_message("You cannot draw a card; Uno is pending.")

        if self.waiting_for_seven:
            self.send_message("You cannot draw a card; a seven is pending.")

        self.last_num_cards_drawn = 0

        card = self.deck.draw_card()
        self.last_num_cards_drawn += 1

        if self.advanced_rules:
            while not self.deck.check_valid_play(card):
                player.add_card(card)
                card = self.deck.draw_card()
                self.last_num_cards_drawn += 1
            player.add_card(card)
        else:
            player.add_card(card)
        return True

    def set_wild_color(self, id, c):
        if self.players.get(id, None).get_id() != self.turn:
            self.send_message("It is not currently your turn!")
            return False

        if not self.waiting_for_wild:
            self.send_message("An uncolored Wild card is not on top of the played pile.")
            return False

        if id != self.waiting_for_wild_id:
            self.send_message("You cannot set the wild color. Waiting for %s to set it." % self.waiting_for_wild_name)
            return False

        if not c.lower() in ['r', 'y', 'g', 'b']:
            self.send_message("That is not a valid color. Choose R, G, B, or Y.")
            return False

        self.deck.set_wild(c)
        self.waiting_for_wild = False
        self.waiting_for_wild_id = ""

        return True

    def set_uno_pending(self, val, id):
        if val != True and val != False:
            self.send_message("Uno pending must be a Boolean value.")
            return

        self.uno_pending = val
        self.uno_pending_id = id

    def is_wild_pending(self):
        return self.waiting_for_wild

    def list_players(self):
        text = "List of players:\n\n"
        for p in self.players.keys():
            text += p + (" [*]" if self.players[p].get_id() == self.turn else "") + "\n"
        return text

    def get_player(self, id):
        return self.players.get(id, None)

    def get_players(self):
        return self.players_and_names

    def get_topmost_card(self):
        return self.deck.get_topmost_card()

    def get_state(self):
        text = "Current Turn: " + self.get_player_name_by_num(self.turn) + "\n"
        top_card = self.get_topmost_card()
        if top_card is None:
            text += "Topmost Card: None"
        else:
            text += "Topmost Card: " + str(top_card)
        return text