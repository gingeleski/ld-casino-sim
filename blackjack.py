"""
blackjack.py

Simulator for online live dealer blackjack at the Golden Nugget
"""

import random
import math
import os
import sys

import matplotlib.pyplot as plt

STARTING_BANKROLL = 5000
DECKS_PER_SHOE = 8
NUMBER_OF_OTHER_PLAYERS = 5
PENETRATION = 0.50  # Dealer plays 50% of shoe then shuffles
HIT_SPLIT_ACES = False
NORMAL_BET_AMOUNT = 25
BET_ONLY_WHEN_FAVORABLE_COUNT = False
CARD_COUNTING_SYSTEM = 'WONG_HALVES'  # WONG_HALVES, HI_LO
FAVORABLE_COUNT_THRESHOLD = 1.0
COUNT_THE_PP_SIDE_BET = False
PP_EV_THRESHOLD = 0.0
COUNT_THE_PLUS3_SIDE_BET = False
PLUS3_EV_THRESHOLD = 0.0

# TODO appropriate these original params below
"""
BLACKJACK_PAYOUT = 1.5  # 3:2
DEALER_HITS_SOFT_17 = True
LATE_SURRENDER = False
RESPLITS_ALLOWED = False
DOUBLE_AFTER_SPLIT = True
DOUBLE_ON_ANY_TWO_CARDS = True
"""

def play():
    bankroll = STARTING_BANKROLL
    shoe = fill_shoe(DECKS_PER_SHOE)
    random.shuffle(shoe)
    starting_number_of_cards = len(shoe)
    count = 0.0
    pnl = 0.0
    hands_played = 0
    hands_sat_out = 0
    while (float(len(shoe)) / float(starting_number_of_cards)) > (1 - PENETRATION):
        bet_amt, pp_amt, plus3_amt = get_bet_amount(count, shoe, bankroll)
        players_hands = [{'hand':[],'bet_amt':bet_amt}]
        players_hands, dealer_hand, count = deal_round(shoe, players_hands, count)
        outcome, count = play_round(shoe, players_hands, dealer_hand, count, bet_amt)
        pnl += outcome
        bankroll += outcome
    return pnl

def play_round(shoe, players_hands, dealer_hand, count, bet_amt):
    dealer_up_card = dealer_hand[0][0]
    dealer_down_card = dealer_hand[1][0]

    outcome = 0 # Net win/loss after each round, need to account for insurance
    split_count = 0 # Ensure we don't split more than twice
    splits_indices = [] # Pull the right hands out of player's hand list once they're split
    aces_split = False # Under certain circumstances we ensure only 1 more card after split aces

    for player_hand in players_hands:
        if HIT_SPLIT_ACES == False and aces_split == True:
            break  # Here can only get 1 more card after split aces

        true_count = get_true_count(count, shoe)
        round_count = 0 # Track whether we're on first 2 cards or not
        while True:
            decision, insurance = get_decision(dealer_up_card, player_hand['hand'], true_count, split_count, round_count)

            dealer_has_bj = False
            if dealer_up_card == 'A' and (dealer_down_card == 'T' or dealer_down_card == 'J' or dealer_down_card == 'Q' or dealer_down_card == 'K'):
                dealer_has_bj = True
            elif dealer_down_card == 'A' and (dealer_up_card == 'T' or dealer_up_card == 'J' or dealer_up_card == 'Q' or dealer_up_card == 'K'):
                dealer_has_bj = True

            if insurance:
                if decision == 'blackjack': # Take even money
                    count = count_this_card(dealer_down_card, count)
                    return bet_amt, count
                elif dealer_has_bj: # And player doesn't have blackjack
                    count = count_this_card(dealer_down_card, count)
                    return 0, count
                else: # Neither have blackjack
                    outcome -= (bet_amt / 2.0)
            elif dealer_has_bj:
                count = count_this_card(dealer_down_card, count)
                if decision == 'blackjack':
                    return 0, count
                else:
                    return -bet_amt, count
            elif decision == 'blackjack':
                count = count_this_card(dealer_down_card, count)
                return (bet_amt * 1.5), count

            if decision == 'split':
                split_count += 1
                splits_indices.append(players_hands.index(player_hand))
                if player_hand['hand'][0][0] == 'A':
                    aces_split = True
                next_card = get_card(shoe)
                count = count_this_card(next_card, count)
                players_hands.append({'hand':[player_hand['hand'][0], next_card],'bet_amt':bet_amt})
                next_card = get_card(shoe)
                count = count_this_card(next_card, count)
                players_hands.append({'hand':[player_hand['hand'][1], next_card],'bet_amt':bet_amt})
                break
            elif decision == 'double':
                if round_count > 0:
                    # Just hit
                    next_card = get_card(shoe)
                    count = count_this_card(next_card, count)
                    player_hand['hand'].append(next_card)
                    player_current_total, softhard_player, splittable = get_current_total(player_hand['hand'])
                    if player_current_total > 21:
                        break
                else:
                    next_card = get_card(shoe)
                    count = count_this_card(next_card, count)
                    player_hand['hand'].append(next_card)
                    player_hand['bet_amt'] += bet_amt
                    break
            elif decision == 'hit':
                next_card = get_card(shoe)
                count = count_this_card(next_card, count)
                player_hand['hand'].append(next_card)
                player_current_total, softhard_player, splittable = get_current_total(player_hand['hand'])
                round_count += 1
                if player_current_total > 21:
                    break
            elif decision == 'surrender':
                if round_count > 0:
                    # Just hit
                    next_card = get_card(shoe)
                    count = count_this_card(next_card, count)
                    player_hand['hand'].append(next_card)
                    player_current_total, softhard_player, splittable = get_current_total(player_hand['hand'])
                    if player_current_total > 21:
                        break
                else:
                    # Halve bet amount, treat as a bust by adding fake 10 to hand
                    player_hand['bet_amt'] -= bet_amt * 0.5
                    player_hand['hand'].append('Tx')
                    break

            elif decision == 'stand':
                break

    for index in reversed(splits_indices): # Remove hands that were split
        players_hands.pop(index)

    dealer_hand, count = play_dealer_hand(dealer_hand, shoe, count)
    this_round_outcome = round_outcome(players_hands, dealer_hand)
    outcome += this_round_outcome

    return outcome, count

def play_dealer_hand(dealer_hand, shoe, count):
    count = count_this_card(dealer_hand[1], count)
    while True:
        dealer_current_total, softhard_dealer, splittable = get_current_total(dealer_hand)
        if (dealer_current_total < 17):
            next_card = get_card(shoe)
            count = count_this_card(next_card, count)
            dealer_hand.append(next_card)
        else:
            break
    return dealer_hand, count

def round_outcome(players_hands, dealer_hand):
    outcome = 0
    for player_hand in players_hands:
        player_current_total, softhard_player, splittable = get_current_total(player_hand['hand'])
        dealer_current_total, softhard_dealer, splittable = get_current_total(dealer_hand)
        if player_current_total > 21:
            outcome -= player_hand['bet_amt']
        elif player_current_total > dealer_current_total or (dealer_current_total > 21):
            outcome += player_hand['bet_amt']
        elif player_current_total == dealer_current_total:
            continue
        elif player_current_total < dealer_current_total:
            outcome -= player_hand['bet_amt']
    return outcome

## H17 ##
"""
#form: splits_table[player_card_pair][dealer_card]
splits_table = {'2': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '3': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '4': {'2':'N','3':'N','4':'N','5':'Y','6':'Y','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '5': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '6': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '7': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '8': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'Y','9':'Y','T':'Y','J':'Y','Q':'Y','K':'Y','A':'Y'},
                '9': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'N','8':'Y','9':'Y','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'T': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'J': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'Q': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'K': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'A': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'Y','9':'Y','T':'Y','J':'Y','Q':'Y','K':'Y','A':'Y'}}
#form: softs_table[player_value][dealer_up_card]
softs_table = {13: {'2':'hit','3':'hit','4':'hit','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                14: {'2':'hit','3':'hit','4':'hit','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                15: {'2':'hit','3':'hit','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                16: {'2':'hit','3':'hit','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                17: {'2':'hit','3':'double','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                18: {'2':'double','3':'double','4':'double','5':'double','6':'double','7':'stand','8':'stand','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                19: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'double','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                20: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                21: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'}}
#form: softs_table[player_value][dealer_up_card]
hards_table = {2: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                3: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                4: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                5: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                6: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                7: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                8: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                9: {'2':'hit','3':'double','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                10: {'2':'double','3':'double','4':'double','5':'double','6':'double','7':'double','8':'double','9':'double','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                11: {'2':'double','3':'double','4':'double','5':'double','6':'double','7':'double','8':'double','9':'double','T':'double','J':'double','Q':'double','K':'double','A':'double'},
                12: {'2':'hit','3':'hit','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                13: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                14: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                15: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                16: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                17: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                18: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                19: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                20: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                21: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'}}
"""
## S17, SURRENDER ##
#form: splits_table[player_card_pair][dealer_card]
splits_table = {'2': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '3': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '4': {'2':'N','3':'N','4':'N','5':'Y','6':'Y','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '5': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '6': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '7': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                '8': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'Y','9':'Y','T':'Y','J':'Y','Q':'Y','K':'Y','A':'Y'},
                '9': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'N','8':'Y','9':'Y','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'T': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'J': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'Q': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'K': {'2':'N','3':'N','4':'N','5':'N','6':'N','7':'N','8':'N','9':'N','T':'N','J':'N','Q':'N','K':'N','A':'N'},
                'A': {'2':'Y','3':'Y','4':'Y','5':'Y','6':'Y','7':'Y','8':'Y','9':'Y','T':'Y','J':'Y','Q':'Y','K':'Y','A':'Y'}}

#form: softs_table[player_value][dealer_up_card]
softs_table = {13: {'2':'hit','3':'hit','4':'hit','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                14: {'2':'hit','3':'hit','4':'hit','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                15: {'2':'hit','3':'hit','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                16: {'2':'hit','3':'hit','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                17: {'2':'hit','3':'double','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                18: {'2':'stand','3':'double','4':'double','5':'double','6':'double','7':'stand','8':'stand','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                19: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                20: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                21: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'}}

#form: softs_table[player_value][dealer_up_card]
hards_table = {2: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                3: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                4: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                5: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                6: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                7: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                8: {'2':'hit','3':'hit','4':'hit','5':'hit','6':'hit','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                9: {'2':'hit','3':'double','4':'double','5':'double','6':'double','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                10: {'2':'double','3':'double','4':'double','5':'double','6':'double','7':'double','8':'double','9':'double','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                11: {'2':'double','3':'double','4':'double','5':'double','6':'double','7':'double','8':'double','9':'double','T':'double','J':'double','Q':'double','K':'double','A':'hit'},
                12: {'2':'hit','3':'hit','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                13: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                14: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'hit','J':'hit','Q':'hit','K':'hit','A':'hit'},
                15: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'hit','T':'surrender','J':'surrender','Q':'surrender','K':'surrender','A':'hit'},
                16: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'hit','8':'hit','9':'surrender','T':'surrender','J':'surrender','Q':'surrender','K':'surrender','A':'surrender'},
                17: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                18: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                19: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                20: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'},
                21: {'2':'stand','3':'stand','4':'stand','5':'stand','6':'stand','7':'stand','8':'stand','9':'stand','T':'stand','J':'stand','Q':'stand','K':'stand','A':'stand'}}


def get_decision(dealer_up_card, player_hand, true_count, split_count, round_count):
    player_current_total, softhard_player, splittable = get_current_total(player_hand)

    insurance = False
    if round_count == 0:
        # Check insurance
        if dealer_up_card == 'A' and true_count >= 3.0:
            insurance = True
        if player_current_total == 21:
            return 'blackjack', insurance

    # Check split
    if splittable and split_count < 2:
        pair_value = player_hand[0][0]
        split_or_not = splits_table[pair_value][dealer_up_card]
        if split_or_not == 'Y':
            return 'split', insurance
        elif (pair_value == 'T' or pair_value == 'J' or pair_value == 'Q' or pair_value == 'K'):
            if dealer_up_card == '4' and true_count >= 6.0:
                return 'split', insurance
            elif dealer_up_card == '5' and true_count >= 5.0:
                return 'split', insurance
            elif dealer_up_card == '6' and true_count >= 4.0:
                return 'split', insurance

    # Strategy adjustments based on count
    if true_count <= 0.0:
        if player_current_total == 12 and dealer_up_card == '4':
            return 'hit', insurance
        elif softhard_player == 'soft' and player_current_total == 19:
            return 'stand', insurance
        if true_count <= -1.0:
            if player_current_total == 13 and dealer_up_card == '2':
                return 'hit', insurance
    elif true_count > 0.0:
        if player_current_total == 16 and (dealer_up_card == 'T' or dealer_up_card == 'J' or dealer_up_card == 'Q' or dealer_up_card == 'K'):
            return 'stand', insurance
        if true_count >= 1.0:
            if (softhard_player == 'soft' and player_current_total == 19) and dealer_up_card == 5:
                return 'double', insurance
            elif (softhard_player == 'soft' and player_current_total == 17) and dealer_up_card == 2:
                return 'double', insurance
            elif player_current_total == 9 and dealer_up_card == '2':
                return 'double', insurance
            if true_count >= 2.0:
                if player_current_total == 12 and dealer_up_card == '3':
                    return 'stand', insurance
                elif player_current_total == 8 and dealer_up_card == '6':
                    return 'double', insurance
                if true_count >= 3.0:
                    if (softhard_player == 'soft' and player_current_total == 19) and dealer_up_card == 4:
                        return 'double', insurance
                    elif player_current_total == 16 and dealer_up_card == 'A':
                        return 'stand', insurance
                    elif player_current_total == 12 and dealer_up_card == '2':
                        return 'stand', insurance
                    elif player_current_total == 10 and dealer_up_card == 'A':
                        return 'double', insurance
                    elif player_current_total == 9 and dealer_up_card == '7':
                        return 'double', insurance
                    if true_count >= 4.0:
                        if player_current_total == 16 and dealer_up_card == '9':
                                return 'stand', insurance
                        elif player_current_total == 15 and (dealer_up_card == 'T' or dealer_up_card == 'J' or dealer_up_card == 'Q' or dealer_up_card == 'K'):
                            return 'stand', insurance
                        elif player_current_total == 10 and (dealer_up_card == 'T' or dealer_up_card == 'J' or dealer_up_card == 'Q' or dealer_up_card == 'K'):
                            return 'double', insurance
                        if true_count >= 5.0:
                            if player_current_total == 15 and dealer_up_card == 'A':
                                return 'stand', insurance

    # If no split or adjustment should be made based on count, play basic strategy
    if softhard_player == 'soft':
        return softs_table[player_current_total][dealer_up_card], insurance
    elif softhard_player == 'hard':
        return hards_table[player_current_total][dealer_up_card], insurance

def get_current_total(player_hand):
    softhard = 'hard'
    ace_count = 0
    value = 0
    for card in player_hand:
        card_val = card[0]
        if card_val == 'A':
            value += 11
            softhard = 'soft'
            ace_count += 1
        elif card_val == 'K' or card_val == 'Q' or card_val == 'J' or card_val == 'T':
            value += 10
        else:
            this_val = int(card_val)
            value += this_val
    non_soft_value = value
    for x in range(0,ace_count):
        if value > 21 and softhard == 'soft':
            value -= 10
        non_soft_value -= 10
    if non_soft_value >= 11 and softhard == 'soft':
        softhard = 'hard'
    splittable = False
    if player_hand[0][0] == player_hand[1][0]:
        splittable = True
    return value, softhard, splittable

def get_true_count(count, shoe):
    decks_remaining = float(len(shoe)) / 52.0
    return float(count) / decks_remaining

def deal_round(shoe, players_hands, count):
    for player_hand in players_hands:
        next_card = get_card(shoe)
        count = count_this_card(next_card, count)
        player_hand['hand'].append(next_card)
        next_card = get_card(shoe)
        count = count_this_card(next_card, count)
        player_hand['hand'].append(next_card)
    dealer_hand = []
    next_card = get_card(shoe)
    dealer_hand.append(next_card)
    count = count_this_card(next_card, count)
    next_card = get_card(shoe)
    dealer_hand.append(next_card)
    # Don't count this yet - player can't see it...
    return players_hands, dealer_hand, count

def count_this_card(card, count):
    card_val = card[0]
    # FIXME there's a bug where rarely you get a card like '7' instead of '7h', etc...
    card_suit = None
    if len(card) > 1:     
        card_suit = card[1]
    if CARD_COUNTING_SYSTEM == 'HI_LO':
        # Hi-lo system (Level I)
        if card_val == 'A' or card_val == 'K' or card_val == 'Q' or card_val == 'J' or card_val == 'T':
            return count - 1.0
        elif card_val == '6' or card_val == '5' or card_val == '4' or card_val == '3' or card_val == '2':
            return count + 1.0
        # Otherwise count stays the same so...
    elif CARD_COUNTING_SYSTEM == 'WONG_HALVES':
        # Stanford Wong's Halves system (Level III)
        if card_val == 'T' or card_val == 'J' or card_val == 'Q' or card_val == 'K' or card_val == 'A':
            return count - 1.0
        elif card_val == '2' or card_val == '7':
            return count + 0.5
        elif card_val == '3' or card_val == '4' or card_val == '6':
            return count + 1.0
        elif card_val == '5':
            return count + 1.5
        elif card_val == '9':
            return count - 0.5
        # And 8's don't affect the count so...
    return count

def fill_shoe(decks):
    new_deck = ['As','2s','3s','4s','5s','6s','7s','8s','9s','Ts','Js','Qs','Ks',
            'Ah','2h','3h','4h','5h','6h','7h','8h','9h','Th','Jh','Qh','Kh',
            'Ad','2d','3d','4d','5d','6d','7d','8d','9d','Td','Jd','Qd','Kd',
            'Ac','2c','3c','4c','5c','6c','7c','8c','9c','Tc','Jc','Qc','Kc']
    shoe = []
    for x in range(0,decks):
        shoe.extend(new_deck)
    return shoe

def get_card(shoe):
    if len(shoe) > 0:
        return shoe.pop(0)
    else:
        return None

def get_pp_ev(shoe):
    # TODO
    return 0

def get_plus3_ev(shoe):
    # TODO
    return 0

def get_bet_amount(count, shoe, bankroll):
    true_count = get_true_count(count, shoe)
    bet_amt = 0
    pp_amt = 0
    plus3_amt = 0
    if BET_ONLY_WHEN_FAVORABLE_COUNT:
        if true_count > FAVORABLE_COUNT_THRESHOLD:
            bet_amt = NORMAL_BET_AMOUNT
        else:
            return bet_amt, pp_amt, plus3_amt  # Sit out with 0 bets
    else:
        bet_amt = NORMAL_BET_AMOUNT
    if COUNT_THE_PP_SIDE_BET:
        pp_ev = get_pp_ev(shoe)
        if pp_ev > PP_EV_THRESHOLD:
            pp_ev = bet_amt
    if COUNT_THE_PLUS3_SIDE_BET:
        plus3_ev = get_plus3_ev(shoe)
        if plus3_ev > PLUS3_EV_THRESHOLD:
            plus3_ev = bet_amt
    return bet_amt, pp_amt, plus3_amt

def main():
    # Simulate 12 shoes
    for i in range(0,12):
        pnl = play()
        print('shoe ' + str(i+1))
        print('pnl: ' + str(pnl))
        print('---')

if __name__=='__main__':
    main()
