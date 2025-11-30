import re
regex = re.compile(r'(\s+)(\d+)(\s+)(\w+)(\s+)(\d+)(\s+)(\w+)(\s+)(\w+)(\s+)(\d+)(\s+)([-\s][0-9]\.\d+)(\s+)(\d+\.\d+|\d+)(\n|\s+)')

f1 = open("processed_mod.top", 'w')
f0 = open("processed.top", 'r')

while True:
    line = f0.readline()
    if not line: break
    matchobj = regex.search(line)
    if matchobj != None:

# 4th item is atom !
        if "H" != matchobj[4][0]:
            f1.write(matchobj[1] + matchobj[2] + matchobj[3] + matchobj[4] + "_" + matchobj[5][1:]+ matchobj[6] + matchobj[7] + matchobj[8] + matchobj[9] + matchobj[10] + matchobj[11] + matchobj[12] + matchobj[13] + matchobj[14] + matchobj[15] + matchobj[16] + "\n")
        else:
            f1.write(matchobj[1] + matchobj[2] + matchobj[3] + matchobj[4] + "_" + matchobj[5][1:]+ matchobj[6] + matchobj[7] + matchobj[8] + matchobj[9] + matchobj[10] + matchobj[11] + matchobj[12] + matchobj[13] + matchobj[14] + matchobj[15] + matchobj[16] + "\n")
            #f1.write(line)
    else:
        f1.write(line)
f0.close()
f1.close()
