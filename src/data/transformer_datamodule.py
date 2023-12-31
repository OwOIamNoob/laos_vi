from argparse import ArgumentError
from typing import Optional, Tuple
import hydra, omegaconf
from omegaconf import DictConfig
import os
import torch
from pathlib import Path
from pytorch_lightning import LightningDataModule
from torch.utils.data import ConcatDataset, DataLoader, Dataset, random_split
from transformers import DataCollatorWithPadding

import pyrootutils
pyrootutils.setup_root(search_from=__file__, 
                       indicator="pyproject.toml",
                       pythonpath=True)
#functional imports
from laonlp.tokenize import word_tokenize
import pyvi
from src.data.components.dataset import *
from src.data.components.vocab import Vocab
import numpy as np


class TransformerDataModule(LightningDataModule):
    """
    LightningDataModule for HF Datasets.
    Requires a pre-processed (tokenized, cleaned...) dataset provided within the `data` folder.
    Might require adjustments if your dataset doesn't follow the structure of SNLI or MNLI.

    A DataModule implements 5 key methods:
        - prepare_data (things to do on 1 GPU/TPU, not on every GPU/TPU in distributed mode)
        - setup (things to do on every accelerator in distributed mode)
        - train_dataloader (the training dataloader)
        - val_dataloader (the validation dataloader(s))
        - test_dataloader (the test dataloader(s))

    This allows you to share a full dataset without explaining how to download,
    split, transform and process the data.

    Read the docs:
        https://pytorch-lightning.readthedocs.io/en/latest/extensions/datamodules.html
    """

    def __init__(
        self,
        data_dir: str,
        input_vocab: str,
        target_vocab: str,
        suffix: list = ['clean'],
        batch_size: int = 64,
        max_length: int = 256,
        num_workers: int = 2,
        pin_memory: bool = False,):
        super().__init__()

        # this line allows to access init params with 'self.hparams' attribute
        # it also ensures init params will be stored in ckpt
        self.save_hyperparameters(logger=False)
        
        self.input_vocab = None
        self.target_vocab = None
        
        self.train_dataset = None
        self.test_dataset = None
        self.val_dataset = None
        
        self.collator_fn = None
        self.setup()

    def prepare_data(self):
        """
        We should not assign anything here, so this function simply ensures
        that the pre-processed data is available.
        """
        pass
        

    def setup(self, stage: Optional[str] = None):
        """Load data. Set variables: `self.data_train`, `self.data_val`, `self.data_test`.
        This method is called by lightning twice for `trainer.fit()` and `trainer.test()`, so be careful if you do a random split!
        The `stage` can be used to differentiate whether it's called before trainer.fit()` or `trainer.test()`."""

        if not self.input_vocab and not self.target_vocab:
            self.input_vocab = Vocab(vocab_path= self.hparams.input_vocab + ".txt",
                                           weights_path = self.hparams.input_vocab + ".pt",
                                           stride = 1,
                                           init_special_symbol=False,
                                           tokenizer = 'lao')
            
            self.target_vocab = Vocab(  vocab_path=self.hparams.target_vocab + ".txt",
                                        weights_path = self.hparams.target_vocab + ".pt",
                                        init_special_symbol=False,
                                        tokenizer = 'vi')
            

        if not self.train_dataset and not self.test_dataset and not self.val_dataset:
            self.train_dataset = LaosDataset(data_dir = self.hparams.data_dir,
                                             file_type = "dev",
                                             suffix = self.hparams.suffix,
                                             input_vocab = self.input_vocab,
                                             target_vocab = self.target_vocab)
            
            self.val_dataset =  LaosDataset(data_dir = self.hparams.data_dir,
                                             file_type = "dev",
                                             suffix = self.hparams.suffix,
                                             input_vocab = self.input_vocab,
                                             target_vocab = self.target_vocab)
            
            self.test_dataset = LaosDataset(data_dir = self.hparams.data_dir,
                                             file_type = "dev",
                                             suffix = self.hparams.suffix,
                                             input_vocab = self.input_vocab,
                                             target_vocab = self.target_vocab)
        
        if not self.collator_fn:
            self.collator_fn = Collator(masked_language_model=  False, 
                                        sos_id= self.target_vocab.vocab['<sos>'],
                                        eos_id= self.target_vocab.vocab['<eos>'],
                                        pad_id= self.target_vocab.vocab['<pad>'], 
                                        target_vocab_size=  self.target_vocab.vocab_size,
                                        max_length= self.hparams.max_length)

    def train_dataloader(self)  -> DataLoader[any]:
        return DataLoader(
            dataset=    self.train_dataset,
            batch_size= self.hparams.batch_size,
            num_workers=self.hparams.num_workers,
            pin_memory= self.hparams.pin_memory,
            collate_fn= self.collator_fn,
            shuffle=    False,
            sampler=    ClusterSampler(self.train_dataset, self.hparams.batch_size, True),
        )

    def val_dataloader(self)    -> DataLoader[any]:
        return DataLoader(
            dataset=    self.val_dataset,
            batch_size= self.hparams.batch_size,
            num_workers=self.hparams.num_workers,
            pin_memory= self.hparams.pin_memory,
            collate_fn= self.collator_fn,
            shuffle=    False,
            sampler=    ClusterSampler(self.val_dataset, self.hparams.batch_size, False),
        )

    def test_dataloader(self)   -> DataLoader[any]:
        return DataLoader(
            dataset=    self.test_dataset,
            batch_size= self.hparams.batch_size,
            num_workers=self.hparams.num_workers,
            pin_memory= self.hparams.pin_memory,
            collate_fn= self.collator_fn,
            shuffle=    False,
            sampler=    ClusterSampler(self.test_dataset, self.hparams.batch_size, False),
        )
        
    def get_embedding(self):
        return self.input_vocab.embedder
    
    def teardown(self):
        pass

def export_corpus(path, index, words, dim, stride):
    f = open(path, "w")
    f.write(str(len(words)) + "\t" + str(dim) + "\t" + str(stride))
    for idx, word in enumerate(words):
        f.write("\n" + word + "\t" + str(int(idx)))
    f.close()
    
@hydra.main(version_base="1.3", config_path="../../configs", config_name="train.yaml")
def main(cfg: DictConfig) -> Optional[float]:
    # datamodule = hydra.utils.instantiate(cfg.data)
    datamodule = TransformerDataModule(data_dir=cfg.data.data_dir, 
                                       input_vocab=cfg.data.input_vocab,
                                       target_vocab=cfg.data.target_vocab,
                                       suffix=cfg.data.suffix,
                                       batch_size=4,
                                       max_length=256,
                                       num_workers=2,
                                       pin_memory=False)
    train_dataloader = datamodule.train_dataloader()
    batch = next(iter(train_dataloader))
    inp = batch["inputs"]
    tgt = batch["targets"]
    # # torch.set_printoptions(threshold=10_000)
    print(inp.size())
    print(tgt.size())
    # train_dataloader = datamodule.val_dataloader()
    # batch = next(iter(train_dataloader))
    # inp = batch["inputs"]
    # tgt = batch["targets"]
    # # torch.set_printoptions(threshold=10_000)
    # print(inp.size())
    # print(tgt.size())
    # train_dataloader = datamodule.test_dataloader()
    # batch = next(iter(train_dataloader))
    # inp = batch["inputs"]
    # tgt = batch["targets"]
    # # torch.set_printoptions(threshold=10_000)
    # print(inp.size())
    # print(tgt.size())
    # input_indicies, input_corpus = datamodule.input_vocab.get_topk(30000)
    # target_indicies, target_corpus = datamodule.target_vocab.get_topk(10000)
    
    # inp_weights = datamodule.input_vocab.embed(input_indicies[:, 0],"cpu")
    # export_corpus("/work/hpc/potato/laos_vi/data/embedding/laos_15000.txt", input_indicies[:, 0], input_corpus, 100, 3)
    # torch.save(inp_weights, "/work/hpc/potato/laos_vi/data/embedding/laos_15000.pt")
    
    # target_weights = datamodule.target_vocab.embed(target_indicies[:, 0],"cpu")
    # export_corpus("/work/hpc/potato/laos_vi/data/embedding/vi_15000.txt", target_indicies[:, 0], target_corpus, 100, 3)
    # torch.save(target_weights, "/work/hpc/potato/laos_vi/data/embedding/vi_15000.pt")
    return False
    
if __name__ == "__main__":
    main()
    