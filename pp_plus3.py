"""
Perfect Pairs and Plus3 side bet speed tests
"""

import itertools
import random
import timeit

def fill_shoe(decks):
    new_deck = ['As','2s','3s','4s','5s','6s','7s','8s','9s','Ts','Js','Qs','Ks',
            'Ah','2h','3h','4h','5h','6h','7h','8h','9h','Th','Jh','Qh','Kh',
            'Ad','2d','3d','4d','5d','6d','7d','8d','9d','Td','Jd','Qd','Kd',
            'Ac','2c','3c','4c','5c','6c','7c','8c','9c','Tc','Jc','Qc','Kc']
    shoe = []
    for x in range(0,decks):
        shoe.extend(new_deck)
    return shoe

def evaluate_pp(hand):
    c1_suit, c2_suit = hand[0][1], hand[1][1]
    same_suit = (c1_suit == c2_suit)
    c1_rank, c2_rank = hand[0][0], hand[1][0]
    same_rank = (c1_rank == c2_rank)
    if same_suit and same_rank:
        # "Perfect pair" pays 25:1
        return 25
    same_color = False
    if same_suit == False:
        if (c1_suit == 's' or c1_suit == 'c') and (c2_suit == 's' or c2_suit == 'c'):
            # Both spade or club -> black
            same_color = True
        elif (c1_suit == 'h' or c1_suit == 'd') and (c2_suit == 'h' or c2_suit == 'd'):
            # Both heart or diamond -> red
            same_color = True            
    if same_color and same_rank:
        # Same color pair pays 12:1
        return 12
    elif same_rank:
        # Mixed color pair pays 6:1
        return 6
    # Don't have anything so lost the 1 unit
    return -1

def evaluate_plus3(hand):
    c1_rank, c2_rank, c3_rank = hand[0][0], hand[1][0], hand[2][0]
    c1_suit, c2_suit, c3_suit = hand[0][1], hand[1][1], hand[2][1]
    same_rank = (c1_rank == c2_rank == c3_rank)
    same_suit = (c1_suit == c2_suit == c3_suit)
    if same_rank and same_suit:
        # Suited three-of-a-kind pays 100:1
        return 100
    elif same_rank:
        # Three-of-a-kind pays 25:1
        return 25
    strts = ['A23','234','345','456','567','678','789','89T','9TJ','TJQ','JQK','QKA']
    strt_eval = c1_rank + c2_rank + c3_rank
    strt_eval_perms = [''.join(p) for p in itertools.permutations(strt_eval)]
    is_strt = False
    for p in strt_eval_perms:
        if p in strts:
            is_strt = True
            break
    if same_suit and is_strt:
        # Straight flush pays 40:1
        return 40
    elif is_strt:
        # Straight pays 10:1
        return 10
    elif same_suit:
        # Flush pays 5:1
        return 5
    # Don't have anything so lost the 1 unit
    return -1

def get_ev_of_pp(shoe):
    permutations = itertools.combinations(shoe, 2)
    yield_ = 0
    for permutation in permutations:
        yield_ += evaluate_pp(permutation)

def get_ev_of_plus3(shoe):
    permutations = itertools.combinations(shoe, 3)
    yield_ = 0
    for permutation in permutations:
        yield_ += evaluate_plus3(permutation)


if __name__ == '__main__':
    setup = 'from __main__ import get_ev_of_pp, '
    setup += 'get_ev_of_plus3, '
    setup += 'fill_shoe, '
    setup += 'evaluate_pp, '
    setup += 'evaluate_plus3' + '\n'
    setup += 'import itertools' + '\n'
    setup += 'import random' + '\n'
    setup += 'shoe = fill_shoe(8)' + '\n'
    setup += 'random.shuffle(shoe)'
    print('PERFECT PAIRS EVALUATION, 8-DECK SHOE')
    RUNS_TO_DO = 100
    print('\t' + 'Avg runtime over ' + str(RUNS_TO_DO) + ' sessions (s) = ', end='')
    total_runtime = timeit.timeit('get_ev_of_pp(shoe)', setup=setup, number=RUNS_TO_DO)
    print(str(float(total_runtime / float(RUNS_TO_DO))))
    print('PLUS3 EVALUATION, 8-DECK SHOE')
    print('\t' + 'Avg runtime over ' + str(RUNS_TO_DO) + ' sessions (s) = ', end='')
    total_runtime = timeit.timeit('get_ev_of_plus3(shoe)', setup=setup, number=1)
    print(str(float(total_runtime / float(RUNS_TO_DO))))
