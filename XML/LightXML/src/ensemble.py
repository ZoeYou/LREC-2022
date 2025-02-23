import torch
from torch.utils.data import DataLoader
from dataset import MDataset, createDataCSV

from model import LightXML

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str, required=True)
parser.add_argument('--modelname', type=str, required=False, help='Name of the model (just in case that model and dataset do not have the same name).')
parser.add_argument('--label_file', type=str, required=False, default='../../data/ipc-sections/20210101/labels_group_id_6.tsv')
args = parser.parse_args()

if __name__ == '__main__':
    ###org: df, label_map = createDataCSV(args.dataset) 
    df, _ = createDataCSV(args.dataset)

    ### use original label map (label_file) instead of label map created by createDataCSV
    labels = [l.split("\t")[0] for l in open(args.label_file).read().splitlines()[1:]]
    label_map = {}
    for i, label in enumerate(labels):
        label_map[str(i)] = i
     
    print(f'load {args.dataset} dataset with '
          f'{len(df[df.dataType =="train"])} train {len(df[df.dataType =="test"])} test with {len(label_map)} labels done')

    predicts = []
    if "-fr-" in args.dataset or "INPI" in args.dataset or ("-en-" in args.dataset and "translated" in args.dataset):
        berts = ['xlm-roberta', 'camembert', 'mbert']#, 'camembert-large'] #xlm-roberta-large', 
    else:
        berts = ['bert-base', 'roberta', 'xlnet'] 
      
    for index in range(len(berts)):
        if args.modelname:
            model_name = [args.modelname, '' if berts[index] == 'bert-base' else berts[index]] 
        else:
            model_name = [args.dataset, '' if berts[index] == 'bert-base' else berts[index]]
        model_name = '_'.join([i for i in model_name if i != ''])

        model = LightXML(n_labels=len(label_map), bert=berts[index])

        print(f'models/model-{model_name}.bin')
        model.load_state_dict(torch.load(f'models/model-{model_name}.bin'), strict=False)


        tokenizer = model.get_tokenizer()
        test_d = MDataset(df, 'test', tokenizer, label_map, 512)
        testloader = DataLoader(test_d, batch_size=16, num_workers=0,
                                shuffle=False)

        model.cuda()
        predicts.append(torch.Tensor(model.one_epoch(0, testloader, None, mode='test')[0]))

    df = df[df.dataType == 'test']

    total = len(df)
    acc1 = [0 for i in range(len(berts) + 1)]
    acc3 = [0 for i in range(len(berts) + 1)]
    acc5 = [0 for i in range(len(berts) + 1)]

    # save this for error analysis
    preds = []
    nb_true_labels = 0
    for index, true_labels in enumerate(df.label.values):
        true_labels = set([label_map[i] for i in true_labels.split()])
        nb_true_labels += len(true_labels)

        logits = [torch.sigmoid(predicts[i][index]) for i in range(len(berts))] 
        logits.append(sum(logits))
        
        logits = [(-i).argsort()[:10].cpu().numpy() for i in logits]

        for i, logit in enumerate(logits):
            acc1[i] += len(set([logit[0]]) & true_labels)
            acc3[i] += len(set(logit[:3]) & true_labels)
            acc5[i] += len(set(logit[:5]) & true_labels)
            

        preds.append(logit[0])


    with open(f'./results/{args.dataset}.out', 'w') as f:
        for i, name in enumerate(berts + ['all']):
            p1 = acc1[i] / total
            p3 = acc3[i] / total / 3
            p5 = acc5[i] / total / 5

            r1 = acc1 / nb_true_labels
            r3 = acc3 / nb_true_labels
            r5 = acc5 / nb_true_labels

            print(f'{name} P@1:{p1}, P@3:{p3}, P@5:{p5}, R@1:{r1}, R@3:{r3}, R@5:{r5}', file=f)
            print(f'{name} P@1:{p1}, P@3:{p3}, P@5:{p5}, R@1:{r1}, R@3:{r3}, R@5:{r5}')


    with open(f'./results/{args.dataset}_pred.txt', 'w') as out_f:
        lines = [str(l) for l in preds]
        out_f.write("\n".join(lines))
