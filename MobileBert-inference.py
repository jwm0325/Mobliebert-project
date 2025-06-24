import torch
import pandas as pd
import numpy as np
from transformers import MobileBertForSequenceClassification, MobileBertTokenizer
from tqdm import tqdm
from collections import defaultdict

GPU = torch.cuda.is_available()
device = torch.device("cuda" if GPU else "cpu")
print("Using device: ", device)

# 데이터
data_path = "gamereview2.csv"
df = pd.read_csv(data_path, encoding="cp949")
data_X = list(df['content'].values)
labels = df['is_positive'].values
game_id = df['app_id'].values

print(len(data_X))

# 토큰화
tokenizer = MobileBertTokenizer.from_pretrained("mobilebert-uncased", do_lower_case=True)
inputs = tokenizer(data_X, truncation=True, max_length=256, add_special_tokens=True, padding="max_length")
inputs_ids = inputs['input_ids']
attention_mask = inputs['attention_mask']
print("데이터셋구축완료")

batch_size = 8

# game_id도 tensor로 만들어서 TensorDataset에 추가
test_inputs = torch.tensor(inputs_ids)
test_labels = torch.tensor(labels)
test_masks = torch.tensor(attention_mask)
test_game_id = torch.tensor(game_id)

test_data = torch.utils.data.TensorDataset(test_inputs, test_masks, test_labels, test_game_id)
test_sampler = torch.utils.data.SequentialSampler(test_data)
test_dataloader = torch.utils.data.DataLoader(test_data, sampler=test_sampler, batch_size=batch_size)

# 모델 로드
model = MobileBertForSequenceClassification.from_pretrained("mobilebert_model.pt")
model.to(device)

model.eval()

test_pred = []
test_true = []

loss_per_game = defaultdict(list)

for batch in tqdm(test_dataloader, desc="Inferring Full Dataset with Loss"):
    batch_ids, batch_mask, batch_labels, batch_game_id = batch

    batch_ids = batch_ids.to(device)
    batch_mask = batch_mask.to(device)
    batch_labels = batch_labels.to(device)

    with torch.no_grad():
        outputs = model(batch_ids, attention_mask=batch_mask, labels=batch_labels)
        loss = outputs.loss
        logits = outputs.logits

    pred = torch.argmax(logits, dim=1)
    test_pred.extend(pred.cpu().numpy())
    test_true.extend(batch_labels.cpu().numpy())

    for gid in batch_game_id.numpy():
        loss_per_game[gid].append(loss.item())

df['prediction'] = test_pred

def compute_accuracy(group):
    correct = (group['is_positive'] == group['prediction']).sum()
    total = len(group)
    return round(correct / total, 4)

app_accuracy = df.groupby('app_id').apply(compute_accuracy).reset_index()
app_accuracy.columns = ['app_id', 'accuracy']

avg_loss_per_game = {gid: np.mean(losses) for gid, losses in loss_per_game.items()}
loss_df = pd.DataFrame(list(avg_loss_per_game.items()), columns=['app_id', 'avg_loss'])

print("\n게임별(app_id) 정확도:")
print(app_accuracy)

print("\n게임별 평균 손실:")
print(loss_df)
