import torch
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from transformers import get_linear_schedule_with_warmup, logging
from transformers import MobileBertForSequenceClassification, MobileBertTokenizer
from torch.utils.data import TensorDataset, DataLoader, RandomSampler, SequentialSampler
from tqdm import tqdm

GPU = torch.cuda.is_available()

device = torch.device("cuda" if GPU else "cpu")
print("Using device:", device)

logging.set_verbosity_error()

# 데이터
path = "gamereview2.csv"
df = pd.read_csv(path, encoding="cp949")
data_X = list(df['content'].values)
labels = df['is_positive'].values
game_id = df['app_id'].values

print("### 데이터 샘플 ###")
print("리뷰 문장: ", data_X[:5])
print("긍정/부정 : ", labels[:5])

#토큰화
tokenizer = MobileBertTokenizer.from_pretrained('mobilebert-uncased', do_lower_case=True)
inputs = tokenizer(data_X, truncation=True, max_length=256, add_special_tokens=True, padding="max_length")
input_ids = inputs['input_ids']
attention_mask = inputs['attention_mask']

num_to_print = 3
print("\n### 토큰화 결과 샘플 ###")
for j in range(num_to_print):
    print(f"\n{j + 1}번째 데이터")
    print("데이터 : ", data_X[j])
    print("토큰 : ", input_ids[j])
    print("어텐션 마스크 : ", attention_mask[j])

# 학습용 및 검증용 데이터셋 분리(scikit learn에 있는 train_test_split 함수 사용, random_state는 반드시 일치시킬 것)
train, validation, train_y, validation_y, train_game_id, val_game_id = (train_test_split
                                                                        (input_ids, labels,game_id, test_size=0.2, random_state=2025))
train_mask, validation_mask = train_test_split(attention_mask, test_size=0.2, random_state=2025)

# batch_size는 한 번에 학습하는 데이터의 양
batch_size = 8

# 학습용 데이터로터 구현(torch tensor)
train_inputs = torch.tensor(train)
train_labels = torch.tensor(train_y)
train_masks = torch.tensor(train_mask)
train_data = TensorDataset(train_inputs, train_masks, train_labels)
train_sampler = RandomSampler(train_data)
train_dataloader = DataLoader(train_data, sampler=train_sampler, batch_size=batch_size)
# 검증 데이터로더 구현
validation_inputs = torch.tensor(validation)
validation_labels = torch.tensor(validation_y)
validation_masks = torch.tensor(validation_mask)
validation_data = TensorDataset(validation_inputs, validation_masks, validation_labels)
validation_sampler = SequentialSampler(validation_data)
validation_dataloader = DataLoader(validation_data, sampler=validation_sampler, batch_size=batch_size)
# 모델 설정
model = MobileBertForSequenceClassification.from_pretrained('mobilebert-uncased', num_labels=2)
model.to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, eps=1e-8)
epochs = 4
scheduler = get_linear_schedule_with_warmup(optimizer,
                                            num_warmup_steps=0,
                                            num_training_steps=len(train_dataloader) * epochs)


epoch_results = []

for e in range(epochs):
    model.train()
    total_train_loss = 0
# 모델 학습
    progress_bar = tqdm(train_dataloader, desc=f"Training Epoch {e + 1}", leave=True)
    for batch in progress_bar:
        batch_ids, batch_mask, batch_labels = batch

        batch_ids = batch_ids.to(device)
        batch_mask = batch_mask.to(device)
        batch_labels = batch_labels.to(device)

        model.zero_grad()

        output = model(batch_ids, attention_mask=batch_mask, labels=batch_labels)
        loss = output.loss
        total_train_loss += loss.item()

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        progress_bar.set_postfix({'loss': loss.item()})

    avg_train_loss = total_train_loss / len(train_dataloader)

    model.eval()

    train_pred = []
    train_true = []
# 훈련 데이터 성능 평가
    for batch in tqdm(train_dataloader, desc=f"Evaluation Train Epoch {e + 1}", leave=True):
        batch_ids, batch_mask, batch_labels = batch

        batch_ids = batch_ids.to(device)
        batch_mask = batch_mask.to(device)
        batch_labels = batch_labels.to(device)

        with torch.no_grad():
            output = model(batch_ids, attention_mask=batch_mask)
        logits = output.logits
        pred = torch.argmax(logits, dim=1)
        train_pred.extend(pred.cpu().numpy())
        train_true.extend(batch_labels.cpu().numpy())

    train_accuracy = np.sum(np.array(train_pred) == np.array(train_true)) / len(train_pred)

    val_pred = []
    val_true = []
# 데이터 검증
    for batch in tqdm(validation_dataloader, desc=f"Evaluation Validation Epoch {e + 1}", leave=True):
        batch_ids, batch_mask, batch_labels = batch

        batch_ids = batch_ids.to(device)
        batch_mask = batch_mask.to(device)
        batch_labels = batch_labels.to(device)

        with torch.no_grad():
            output = model(batch_ids, attention_mask=batch_mask)
        logits = output.logits
        pred = torch.argmax(logits, dim=1)
        val_pred.extend(pred.cpu().numpy())
        val_true.extend(batch_labels.cpu().numpy())

    val_accuracy = np.sum(np.array(val_pred) == np.array(val_true)) / len(val_pred)

    val_results_df = pd.DataFrame({
        'app_id': val_game_id,
        'true': val_true,
        'pred': val_pred
    })
    accuracy_by_game = val_results_df.groupby('app_id').apply(
        lambda x: np.mean(x['true'] == x['pred'])
    ).reset_index(name='accuracy')

    print(
        f"Epoch {e + 1}: Train loss: {avg_train_loss:.4f}, Train Acc: {train_accuracy:.4f}, Val Acc: {val_accuracy:.4f}")
    print(f"Epoch {e + 1} 게임별 정확도:")
    for _, row in accuracy_by_game.iterrows():
        print(f"  app_id {row['app_id']} 정확도: {row['accuracy']:.4f}")

    epoch_results.append((avg_train_loss, train_accuracy, val_accuracy))



print("\n### 모델 저장 ###")
save_path = "mobilebert_model2"
model.save_pretrained(save_path + '.pt')
print("모델 저장 완료")
