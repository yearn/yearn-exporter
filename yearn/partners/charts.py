from bisect import bisect_right
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import PercentFormatter
from yearn.partners.constants import TIERS

colors = {'blue': '#0657F9', 'yellow': '#FABF06'}


def currency_formatter(value, index):
    powers = [10 ** x for x in (3, 6, 9, 12)]
    suffixes = ['k', 'm', 'b', 't']
    
    if value < powers[0]:
        return f'${value:.0f}'
    
    i = bisect_right(powers, value) - 1

    # drop a decimal place for round values
    if value / powers[i] % 1 < 0.1:
        return f'${value / powers[i]:.0f}{suffixes[i]}'
    else:
        return f'${value / powers[i]:.1f}{suffixes[i]}'


def make_partner_charts(partner, data):
    df = data.copy()
    df['timestamp'] = pd.to_datetime(df.timestamp)
    df = df.set_index('timestamp')

    fig, ax = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
    ax = list(ax)

    # aggregate balance of wrappers
    agg_balance = (
        pd.pivot_table(df, 'balance_usd', 'timestamp', 'vault', 'sum').ffill().sum(axis=1).resample('1D').mean().ffill()
    )
    agg_balance.plot(title=f'yearn x {partner.name}', label='balance, usd', legend=True, ax=ax[0], c=colors['blue'])

    # tier assigned at the end of each day
    daily_tier = df.resample('1D').last().tier.ffill()
    ax.append(
        daily_tier.plot(
            label='partner tier', ax=ax[0], secondary_y=True, legend=True, c=colors['yellow'], drawstyle="steps-post"
        )
    )

    # accumulated earnings
    earnings = (df.vault_price * df.payout).resample('1D').sum().cumsum().ffill()
    earnings.plot(label='earnings, usd', legend=True, ax=ax[1], c=colors['blue'])

    # share of gross revenue
    ratio = (df.payout / df.protocol_fee).resample('1D').mean().ffill()
    ax.append(ratio.plot(label='share of revenue', legend=True, ax=ax[1], secondary_y=True, c=colors['yellow']))

    # trim start date to the first earnings
    xmin = earnings[earnings > 0].index[0] - pd.to_timedelta('2D')
    ax[0].set_xlim(xmin=xmin)
    ax[1].set_xlim(xmin=xmin)

    # only show ticks for valid affiliate tiers
    ax[2].set_yticks(sorted(TIERS.values()))
    ax[2].autoscale_view()

    # axis labels
    ax[0].set_ylabel('aggregate wrapper balance')
    ax[1].set_ylabel('partner earnings')
    ax[2].set_ylabel('partner tier')
    ax[3].set_ylabel('share of gross revenue')

    # axis formatters
    ax[0].yaxis.set_major_formatter(currency_formatter)
    ax[1].yaxis.set_major_formatter(currency_formatter)
    ax[2].yaxis.set_major_formatter(PercentFormatter(1))
    ax[3].yaxis.set_major_formatter(PercentFormatter(1))

    # visual fixes
    for axis in ax[:2]:
        axis.set_facecolor('none')
        axis.set_zorder(2)
        axis.grid(alpha=0.5)

    plt.tight_layout()
    plt.savefig(Path(f'research/partners/{partner.name}/chart.png'), dpi=300, facecolor='white')
    plt.close()
