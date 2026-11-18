# One physical piece relocation. Chess-rule agnostic.
uint8 MOVE=0          # from_square -> to_square
uint8 REMOVE=1        # from_square -> next free graveyard slot (capture / en passant)
uint8 REPLACE=2       # promotion: swap piece_id's model for `promotion` kind, on to_square

string piece_id       # stable simulation id, e.g. white_pawn_e2
string from_square    # e.g. e2
string to_square      # e.g. e4 ('' for REMOVE)
uint8 operation
string promotion      # 'Q','R','B','N' for REPLACE, else ''
