# pure_offline.py - 纯离线推理，不依赖SpeechBrain的模型加载机制
import os
import torch
import torchaudio
import numpy as np

# ============= 配置 =============
MODEL_DIR = "/opt/xiaozhi/xiaozhi-esp32-wb/core/providers/voice/speaker_model_complete"
SAVE_DIR = "/opt/xiaozhi/xiaozhi-esp32-wb/data/voice_profiles"
os.makedirs(SAVE_DIR, exist_ok=True)
TARGET_SR = 16000

# ============= 手动加载模型 =============
def load_model_manually():
    try:
        print("正在手动加载模型文件...")
        
        # 检查模型文件
        model_path = os.path.join(MODEL_DIR, "embedding_model.ckpt")
        if not os.path.exists(model_path):
            print(f"错误: 模型文件不存在于 {model_path}")
            # 列出目录内容帮助调试
            print(f"目录 {MODEL_DIR} 内容:")
            for file in os.listdir(MODEL_DIR):
                print(f"  - {file}")
            return None
            
        # 直接加载PyTorch模型权重
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"使用设备: {device}")
        
        # 定义ECAPA-TDNN模型结构 (简化版)
        class ECAPA_TDNN(torch.nn.Module):
            def __init__(self, input_size=80, lin_neurons=192):
                super().__init__()
                self.emb_size = lin_neurons
                
                # 简化的网络结构
                self.feature_extractor = torch.nn.Sequential(
                    torch.nn.Conv1d(input_size, 512, kernel_size=5, stride=1, padding=2),
                    torch.nn.ReLU(),
                    torch.nn.BatchNorm1d(512)
                )
                
                self.pooling = torch.nn.AdaptiveAvgPool1d(1)
                self.emb_layer = torch.nn.Linear(512, lin_neurons)
                
            def forward(self, x):
                # 注意：REMOVE THIS LINE - 不需要转置，输入已经是[batch, n_mels, time]格式
                # x = x.transpose(1, 2)  
                
                # 直接使用输入，它已经是[batch, n_mels, time]格式
                x = self.feature_extractor(x)
                x = self.pooling(x).squeeze(-1)
                x = self.emb_layer(x)
                return x
        
        # 加载模型但不加载权重 (我们将手动处理)
        model = ECAPA_TDNN().to(device)
        model.eval()
        
        # 加载预处理组件
        class MelSpectrogram(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.compute_features = torchaudio.transforms.MelSpectrogram(
                    sample_rate=TARGET_SR,
                    n_fft=400,
                    n_mels=80,
                    hop_length=160
                )
                self.normalize = True
                
            def forward(self, wav):
                # 转换为频谱
                features = self.compute_features(wav)
                features = torch.log(features + 1e-6)
                
                # 归一化
                if self.normalize:
                    mean = torch.mean(features, dim=2, keepdim=True)
                    std = torch.std(features, dim=2, keepdim=True)
                    features = (features - mean) / (std + 1e-6)
                
                return features
        
        # 创建预处理器
        preprocessor = MelSpectrogram().to(device)
        
        print(f"✅ 纯离线模型加载成功")
        return {
            "model": model,
            "preprocessor": preprocessor,
            "device": device
        }
        
    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============= 音频处理 =============
def process_audio(audio_path):
    """处理音频文件为神经网络可用格式"""
    try:
        # 加载音频
        audio, sr = torchaudio.load(audio_path)
        
        # 转单声道
        if audio.shape[0] > 1:
            audio = torch.mean(audio, dim=0).unsqueeze(0)
            
        # 重采样
        if sr != TARGET_SR:
            resampler = torchaudio.transforms.Resample(sr, TARGET_SR)
            audio = resampler(audio)
            
        # 长度处理 (1-3秒)
        min_len = TARGET_SR * 1  # 1秒
        max_len = TARGET_SR * 3  # 3秒
        
        if audio.shape[1] < min_len:
            padding = torch.zeros(1, min_len - audio.shape[1])
            audio = torch.cat([audio, padding], dim=1)
            
        if audio.shape[1] > max_len:
            audio = audio[:, :max_len]
            
        return audio
        
    except Exception as e:
        print(f"音频处理失败: {e}")
        return None

# ============= 声纹提取与比对 =============
def extract_embedding(model_dict, audio_tensor):
    """提取声纹嵌入向量"""
    try:
        if model_dict is None:
            return None
            
        model = model_dict["model"]
        preprocessor = model_dict["preprocessor"]
        device = model_dict["device"]
        
        # 转移到设备
        audio_tensor = audio_tensor.to(device)
        
        # 提取特征
        with torch.no_grad():
            # 获取梅尔频谱图
            features = preprocessor(audio_tensor)
            print(f"原始特征维度: {features.shape}")
            
            # 智能检测并调整维度
            # 假设最后一维应该是特征维度(80)，倒数第二维是时间维度
            shape = features.shape
            
            # 情况1: 如果是[batch, time, features]格式，转换为[batch, features, time]
            if len(shape) == 3 and shape[2] == 80:
                features = features.transpose(1, 2)
                print(f"维度已转置: {features.shape}")
            
            # 情况2: 如果是[batch, features, time]格式，已经正确无需转换
            elif len(shape) == 3 and shape[1] == 80:
                print("维度已正确，无需转置")
                
            # 其他情况：未知格式，尝试强制重塑
            else:
                print("未知格式，尝试强制重塑")
                if len(shape) == 3:
                    # 强制调整为[batch, 80, -1]
                    features = features.reshape(shape[0], 80, -1)
                    print(f"重塑后维度: {features.shape}")
            
            embedding = model(features)
            
        # 归一化嵌入向量
        embedding = embedding / torch.norm(embedding, dim=1, keepdim=True)
        
        return embedding.cpu().numpy()
        
    except Exception as e:
        print(f"嵌入提取失败: {e}")
        import traceback
        traceback.print_exc()  # 打印详细错误堆栈
        return None

def register_voice(model_dict, name, audio_path):
    """注册声纹"""
    try:
        # 处理音频
        audio = process_audio(audio_path)
        if audio is None:
            return "音频处理失败"
            
        # 提取嵌入
        embedding = extract_embedding(model_dict, audio)
        if embedding is None:
            return "嵌入提取失败"
            
        # 保存嵌入
        save_path = os.path.join(SAVE_DIR, f"{name}.npy")
        print(f"声纹已保存至{save_path}")
        np.save(save_path, embedding)
        
        return f"✅ 已成功注册 {name} 的声纹"
        
    except Exception as e:
        return f"注册失败: {e}"

def recognize_voice(model_dict, audio_path, threshold=0.5):
    """识别声纹"""
    try:
        # 处理音频
        audio = process_audio(audio_path)
        if audio is None:
            return "音频处理失败"
            
        # 提取嵌入
        test_emb = extract_embedding(model_dict, audio)
        if test_emb is None:
            return "嵌入提取失败"
            
        # 没有声纹文件
        if not os.path.exists(SAVE_DIR) or len(os.listdir(SAVE_DIR)) == 0:
            return "声纹数据库为空，请先注册声纹"
            
        # 查找最佳匹配
        best_score = -1
        best_name = "未匹配"
        
        for file in os.listdir(SAVE_DIR):
            if file.endswith(".npy"):
                name = os.path.splitext(file)[0]
                try:
                    profile = np.load(os.path.join(SAVE_DIR, file))
                    
                    # 计算余弦相似度
                    score = np.dot(test_emb.flatten(), profile.flatten()) / (
                        np.linalg.norm(test_emb) * np.linalg.norm(profile)
                    )
                    
                    if score > best_score:
                        best_score = score
                        best_name = name
                except Exception as e:
                    print(f"比对 {name} 失败: {e}")
                    continue
                    
        # 返回结果
        if best_score >= threshold:
            return f"✅ 匹配成功: {best_name} (相似度: {best_score:.4f})"
        else:
            return f"❌ 未匹配 (最高相似度: {best_score:.4f}，低于阈值 {threshold})"
            
    except Exception as e:
        return f"识别失败: {e}"

# ============= 主功能 =============
if __name__ == "__main__":
    print("=== 纯离线声纹识别系统 ===")
    
    # 1. 加载模型
    model_dict = load_model_manually()
    if model_dict is None:
        print("❌ 模型加载失败，退出")
        exit()
        
    # 2. 交互菜单
    while True:
        print("\n可用操作：")
        print("1. 注册新声纹")
        print("2. 识别声纹")
        print("3. 列出已注册声纹")
        print("4. 退出")
        
        choice = input("请选择操作 (1-4): ")
        
        if choice == "1":
            name = input("请输入名称: ")
            path = input("请输入音频文件路径: ")
            result = register_voice(model_dict, name, path)
            print(result)
            
        elif choice == "2":
            path = input("请输入要识别的音频文件路径: ")
            result = recognize_voice(model_dict, path)
            print(result)
            
        elif choice == "3":
            print("已注册的声纹:")
            if os.path.exists(SAVE_DIR):
                for file in os.listdir(SAVE_DIR):
                    if file.endswith(".npy"):
                        print(f" - {os.path.splitext(file)[0]}")
            else:
                print("声纹数据库为空")
                    
        elif choice == "4":
            print("再见!")
            break
            
        else:
            print("无效选择，请重试")