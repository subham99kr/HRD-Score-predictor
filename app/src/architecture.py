import torch
import torch.nn as nn
device = "cuda" if torch.cuda.is_available() else "cpu"

class HybridCNN(nn.Module):
    def __init__(self):
        super().__init__()
        
        self.conv1 = nn.Conv2d(1, 16, 3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.conv3 = nn.Conv2d(32, 64, 3, padding=1)
        
        self.pool = nn.MaxPool2d(2,2)
        self.relu = nn.SiLU()
        
        self.fc_img = nn.Linear(64*8*8,128)
        
        self.fc_feat1 = nn.Linear(23,32)
        self.fc_feat2 = nn.Linear(32,32)
        
        self.fc_final = nn.Linear(160,2)

    def forward(self,img,feat):
        x = self.pool(self.relu(self.conv1(img)))
        x = self.pool(self.relu(self.conv2(x)))
        x = self.pool(self.relu(self.conv3(x)))
        
        x = x.view(x.size(0),-1)
        x = self.relu(self.fc_img(x))
        
        f = self.relu(self.fc_feat1(feat))
        f = self.relu(self.fc_feat2(f))
        
        combined = torch.cat([x,f],dim=1)
        return self.fc_final(combined)
    
def load_medical_model(model_path, device):
    """Utility to load the model correctly into the backend."""
    model = HybridCNN().to(device)
    # map_location ensures it works even if trained on GPU but loaded on CPU
    checkpoint = torch.load(model_path, map_location=device)
    
    # Handling cases where state_dict might be nested
    if "model_state" in checkpoint:
        model.load_state_dict(checkpoint["model_state"])
    else:
        model.load_state_dict(checkpoint)
        
    model.eval()
    return model

