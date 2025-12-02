import csv
from collections import defaultdict

# 데이터 읽기
rep_rates = defaultdict(list)

with open('euvpower_reprate_20251127_0927-20251127_1107.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        freq = float(row['laser_frequency_value'])
        power = float(row['euvChamber_euvPower_value'])
        if power > 0:  # 0이 아닌 값만
            rep_rates[freq].append(power)

# 각 반복률별 평균 계산
print('Rep. Rate (kHz) | Count | Avg EUV Power (W) | Min (W) | Max (W)')
print('=' * 80)
for freq in sorted(rep_rates.keys()):
    powers = rep_rates[freq]
    if len(powers) > 0:
        avg = sum(powers) / len(powers)
        min_p = min(powers)
        max_p = max(powers)
        print(f'{int(freq/1000):3d} | {len(powers):5d} | {avg:.6f} | {min_p:.6f} | {max_p:.6f}')

