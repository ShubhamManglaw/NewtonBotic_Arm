string piece_id
string color          # white | black
string kind           # P R N B Q K
string square         # nearest square if resting on the board within tolerance, else ''
bool upright          # tilt below threshold
bool in_graveyard
geometry_msgs/Pose pose
