import pandas as pd
import re

df = pd.read_csv('output.csv')

df['content'] = df['content'].astype(str)

df = df[df['content'].apply(lambda x: len(x.split()) >= 5)]

df = df[df['content'].apply(lambda x: bool(re.match(r'^[a-zA-Z0-9 ]+$', x)))]

new = df[df['app_id'].isin([570,630,1930,1520,1200,1280,1600,1670,1900,1530,1640,1700,1230,1510,1300,1630,
                            1313,1610,1002,1500,1690,1257,1256,360,1840,30,100,40,1250])].index
df = df.drop(new)

df['is_positive'] = df['is_positive'].replace({'Negative': 0, 'Positive': 1})

df.drop(['id','author_id'],axis=1,inplace=True)


def sample_50_per_class(group):
    # 긍정과 부정으로 나눔
    pos = group[group['is_positive'] == 1]
    neg = group[group['is_positive'] == 0]

    # 둘 다 50개 이상일 때만 진행
    if len(pos) >= 50 and len(neg) >= 50:
        pos_sampled = pos.sample(n=50, random_state=42)
        neg_sampled = neg.sample(n=50, random_state=42)
        return pd.concat([pos_sampled, neg_sampled])
    else:
        # 둘 중 하나라도 부족하면 제외
        return pd.DataFrame()


# 각 app_id 그룹에 적용
balanced_df = df.groupby('app_id', group_keys=False).apply(sample_50_per_class).reset_index(drop=True)

balanced_df.to_csv('gamereview2.csv', index=False)
