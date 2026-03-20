import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--carriage", type=int)
parser.add_argument("--seat", type=str)
args = parser.parse_args()

data = {
    1: [
        { "seat_name": "a1", "isTaken": True },
        { "seat_name": "a2", "isTaken": False },
        { "seat_name": "a3", "isTaken": True },
        { "seat_name": "a4", "isTaken": True },
        { "seat_name": "a5", "isTaken": False },
    ],
    2: [
        { "seat_name": "b1", "isTaken": False },
        { "seat_name": "b2", "isTaken": False },
        { "seat_name": "b3", "isTaken": True },
        { "seat_name": "b4", "isTaken": False },
        { "seat_name": "b5", "isTaken": True },
    ],
    3: [
        { "seat_name": "c1", "isTaken": False },
        { "seat_name": "c2", "isTaken": True },
        { "seat_name": "c3", "isTaken": True },
        { "seat_name": "c4", "isTaken": True },
        { "seat_name": "c5", "isTaken": False },
    ],
}

def chek_availability(carriagenum, seat):
    seatnum = int(seat[-1]) - 1
    carriage = data[carriagenum]
    specific_seat = carriage[seatnum]
    n = 1
    if specific_seat['isTaken'] == False:
        return 'The seat is available'
    else:
        i = 1
        while True:
            if specific_seat["isTaken"] == False:
                    print("The seat ", specific_seat['seat_name'], " is available instead in carriage", carriagenum)
                    break
            if seatnum - i > 0:
                seatnum = seatnum - i
                specific_seat = carriage[seatnum]
                if specific_seat["isTaken"] == False:
                    print("The seat ", specific_seat['seat_name'], " is available instead in carriage", carriagenum)
                    break
                else:
                    seatnum = seatnum + i
            if seatnum + i < 5:
                seatnum = seatnum + i
                specific_seat = carriage[seatnum]
                if specific_seat["isTaken"] == False:
                    print("The seat ", specific_seat['seat_name'], " is available instead in carriage", carriagenum)
                    break
                else:
                    seatnum = seatnum - i
            i = i + 1
            if seatnum + i > 4 and seatnum - i < 0:                
                i = 1
                carriage = data[n]
                carriagenum = n
                seatnum = 0
                specific_seat = carriage[seatnum]
                n = n + 1
                if n > len(data):
                    print("No available seats found.")
                    break


chek_availability(args.carriage, args.seat)