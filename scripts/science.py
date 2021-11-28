import os

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import colors
from yearn.db.models import Block, Session, Snapshot, engine, select


def chart():
    """
    Make yearn.science TVL chart
    """
    plt.rcParams['legend.frameon'] = False
    plt.rcParams['font.family'] = 'Adobe Garamond Pro'
    plt.rcParams['font.style'] = 'italic'
    with Session(engine) as session:
        data = []
        for block, snapshot in session.exec(select(Block, Snapshot).join(Block)):
            data.append({
                'chain_id': block.chain_id,
                'snapshot': block.snapshot,
                'product': snapshot.product,
                'assets': snapshot.assets,
            })

    df = pd.DataFrame(data)
    df = df
    for key in ['product', 'chain_id', ['chain_id', 'product']]:
        pdf = pd.pivot_table(df, 'assets', 'snapshot', key, 'sum').sort_index()
        print(pdf)
        yearn_colors = ['#0657F9', '#FABF06','#23D198', '#EF1E02', '#666666']
        cmap = colors.LinearSegmentedColormap.from_list('yearn', colors=yearn_colors)
        order = ['v2', 'v1', 'earn', 'ib', 'special']
        match key:
            case 'product': pdf[order].plot(stacked=True, kind='area', cmap=cmap, linewidth=0)
            case _: pdf.plot(stacked=True, kind='area', cmap=cmap, linewidth=0)
        
        plt.gca().set_axisbelow(True)
        plt.grid(linewidth=0.5)
        plt.xlabel('')
        plt.ylabel('dollaridoos')
        plt.xlim(xmin=pd.to_datetime('2020-07-17'), xmax=max(pdf.index))
        plt.ylim(ymin=0)
        total = pdf.iloc[-1].sum()
        ath_x = pdf.sum(axis=1).argmax()
        plt.title(f'Yearn TVL is ${total / 1e9:.3f} billion')
        plt.tight_layout()
        os.makedirs('static', exist_ok=True)
        text_key = '_'.join(key) if isinstance(key, list) else key
        plt.savefig(f'static/yearn_{text_key}.png', dpi=300)
