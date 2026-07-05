from pathlib import Path
from point import Point

INPUT_FILE = Path(__file__).with_name("dots.tsv")

def parse_line(line):
    parts = line.split("\t")
    if len(parts) != 3:
        raise ValueError(f"Invalid number of fields ({len(parts)}) in {INPUT_FILE}")
    return Point(parts[0], int(parts[1]), int(parts[2]))

def print_points_on_diagonal(filename, code):
    with open(filename, encoding="utf-8") as f:
        first = True
        for line in f:
            if first:
                first = False
                continue
            point = parse_line(line.strip())
            x = point._x
            y = point._y
            if (4*int(x==y) + 2*int(x==-y) + int(x < 0)) == code:
                print(f"{point.__repr__()}")

if __name__ == "__main__":
    try:
        diagonal = int(input("Diagonal (1, 2, 3, or 4) ?> "))
        # convert to a code, the value of the binary number: (x==y) (x==-y) (x<0)
        # it'll make the point filtering much quicker
        match diagonal:
            case 1:
                code = 4 
            case 2:
                code = 3
            case 3:
                code = 5
            case 4:
                code = 2
            case _:
                raise ValueError(f"Diagonal {diagonal} not in range (1, 2, 3 or 4)!")
        print_points_on_diagonal(INPUT_FILE, code)
    except ValueError as e:
        print(str(e))
