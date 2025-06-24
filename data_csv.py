import pandas as pd
import re

df = pd.read_csv('output.csv')

df['content'] = df['content'].astype(str)

df = df[df['content'].apply(lambda x: len(x.split()) >= 5)]

df = df[df['content'].apply(lambda x: bool(re.match(r'^[a-zA-Z0-9 ]+$', x)))]

new = df[df['app_id'].isin([570,630,1930,1520,1200,1280,1600,1670,1900,1530,1640,1700,1230,1510,1300,1630,
                            1313,1610,1002,1500,1690,1257,1256,360,1840,30,100,40,1250,500,50,80,60])].index
df = df.drop(new)

df['is_positive'] = df['is_positive'].replace({'Negative': 0, 'Positive': 1})

df.drop(['id','author_id'],axis=1,inplace=True)


def balance_reviews(group):
    # 긍정과 부정 리뷰를 나눔
    positive = group[group['is_positive'] == 1]
    negative = group[group['is_positive'] == 0]

    # 더 적은 수에 맞춰 샘플링
    min_count = min(len(positive), len(negative))

    # 샘플링해서 같은 수만큼 유지
    balanced_positive = positive.sample(n=min_count, random_state=42)
    balanced_negative = negative.sample(n=min_count, random_state=42)

    # 합치고 리턴
    return pd.concat([balanced_positive, balanced_negative])


# 각 app_id마다 balance_reviews 함수를 적용
balanced_df = df.groupby('app_id', group_keys=False).apply(balance_reviews).reset_index(drop=True)

balanced_df.to_csv('gamereview1.csv', index=False)
