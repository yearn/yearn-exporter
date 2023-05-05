import os

import matplotlib.pyplot as plt
import pandas as pd
import sentry_sdk
from matplotlib import colors
from y.networks import Network

from yearn.db.models import Block, Session, Snapshot, engine, select

sentry_sdk.set_tag('script','science')


def chart():
    """
    Make yearn.science TVL chart
    """
    plt.rcParams['legend.frameon'] = False
    plt.rcParams['font.family'] = 'Adobe Garamond Pro'
    plt.rcParams['font.style'] = 'italic'
    with Session(engine) as session:
        data = []
        for snap in session.exec(select(Snapshot)):
            data.append({
                'chain_id': Network(snap.block.chain_id).name.lower(),
                'snapshot': snap.block.snapshot,
                'product': snap.product,
                'assets': snap.assets,
            })

    df = pd.DataFrame(data)
    
    # find the last date where all chains are indexed to avoid underreporting tvl
    print('last_indexed', df.groupby('chain_id').snapshot.last(), '', sep='\n')
    last_indexed = df.groupby('chain_id').snapshot.last().min()
    print(df)
    for key in ['product', 'chain_id', ['chain_id', 'product']]:
        pdf = pd.pivot_table(df, 'assets', 'snapshot', key, 'sum').sort_index()[:last_indexed]

        # match with the color scheme
        if key == 'product':
            order = [x for x in ['v2', 'v1', 'earn', 'ib', 'special'] if x in pdf.columns]
            pdf = pdf[order]
        
        yearn_colors = ['#0657F9', '#FABF06','#23D198', '#EF1E02', '#666666']
        cmap = colors.LinearSegmentedColormap.from_list('yearn', colors=yearn_colors)
        pdf.plot(stacked=True, kind='area', cmap=cmap, linewidth=0)
        
        plt.gca().set_axisbelow(True)
        plt.grid(linewidth=0.5)
        plt.xlabel('')
        plt.ylabel('dollaridoos')
        plt.xlim(xmin=pd.to_datetime('2020-07-17'), xmax=last_indexed)
        plt.ylim(ymin=0)
        total = pdf.iloc[-1].sum()
        print(pdf.index[-1])
        plt.title(f'Yearn TVL is ${total / 1e9:.3f} billion')
        plt.tight_layout()
        os.makedirs('static', exist_ok=True)
        text_key = '_'.join(key) if isinstance(key, list) else key
        plt.savefig(f'static/yearn_{text_key}.png', dpi=300)
