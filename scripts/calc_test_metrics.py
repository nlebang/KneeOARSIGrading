import glob
import json
import numpy as np
import os
import argparse
from sklearn.metrics import classification_report, mean_squared_error, balanced_accuracy_score, cohen_kappa_score
from functools import partial
from oarsigrading.evaluation.metrics import bootstrap_ci, plot_confusion


model_dict = {'resnet18': 'Resnet-18',
              'resnet34': 'Resnet-34',
              'resnet50': 'Resnet-50',
              'se_resnet50': 'SE-Resnet-50',
              'se_resnext50_32x4d': 'SE-ResNext50-32x4d',
              'ens_se_resnet50_se_resnext50_32x4d': 'Ensemble'}

features = ['OARSI OST-TL', 'OARSI OST-FL', 'OARSI JSN-L',
            'OARSI OST-TM', 'OARSI OST-FM', 'OARSI JSN-M']


def calc_f1_weighted(y_true, preds, digits=4):
    clf_rep = classification_report(y_true, preds, digits=digits)
    f1_weighted = float(clf_rep.split('\n')[-2].split()[-2])
    return f1_weighted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshots_dir', default='/media/lext/FAST/OARSI_grading_project/workdir/'
                                                   'oarsi_grades_snapshots_weighted/')
    parser.add_argument('--only_first_fu', type=bool, default=False)
    parser.add_argument('--precision', type=int, default=2)
    parser.add_argument('--n_bootstrap', type=int, default=500)
    parser.add_argument('--save_dir', default='/media/lext/FAST/OARSI_grading_project/workdir/Results/pics/')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    for weighted in [False, True]:
        for gwap in [False, True]:
            for gwap_hidden in [False, True]:
                exp = ''
                exp += 'WS_' if weighted else 'NWS_'
                if gwap:
                    exp += 'h-GWAP' if gwap_hidden else 'GWAP'
                else:
                    exp += 'no-GWAP'
                print(exp)
                print('='*80)
                for model in ['ens_se_resnet50_se_resnext50_32x4d']:
                    for snp in glob.glob(os.path.join(args.snapshots_dir, '*', 'test_inference',
                                                      'results_plain.npz')):

                        with open(os.path.join(snp.split('results_plain.npz')[0], 'metrics_plain.json')) as f:
                            test_res = json.load(f)
                            
                        if test_res['model']['backbone'] != model:
                            continue
                        if test_res['model']['weighted_sampling'] != weighted:
                            continue
                        if test_res['model']['gwap'] != gwap:
                            continue
                        if test_res['model']['gwap_hidden'] != gwap_hidden:
                            continue
                        
                        data = np.load(snp)
                        gt = data['gt'].astype(int)

                        if len(features)+1 != gt.shape[1]:
                            continue

                        visits = data['visits']
                        if args.only_first_fu:
                            ind_take = np.array(list(map(lambda x: x == '00', visits)))
                        else:
                            ind_take = np.arange(visits.shape[0], dtype=np.int64)
                        predicts_kl = data['predicts_kl']
                        predicts_oarsi = data['predicts_oarsi']

                        print(f'====> {model} [{snp}]')
                        print(f'=======> KL')

                        kl_preds = predicts_kl[ind_take, :].argmax(1)

                        plot_confusion(gt[ind_take, 0], kl_preds, os.path.join(args.save_dir, 'conf_kl.pdf'))

                        f1_weighted, f1_ci_l, f1_ci_h = bootstrap_ci(partial(calc_f1_weighted, digits=args.precision),
                                                                     gt[ind_take, 0], kl_preds,
                                                                     args.n_bootstrap, seed=args.seed)
                        mse, mse_ci_l, mse_ci_h = bootstrap_ci(mean_squared_error,
                                                               gt[ind_take, 0], kl_preds,
                                                               args.n_bootstrap, seed=args.seed)
                        acc, acc_ci_l, acc_ci_h = bootstrap_ci(balanced_accuracy_score,
                                                               gt[ind_take, 0], kl_preds,
                                                               args.n_bootstrap, seed=args.seed)
                        kappa, kappa_ci_l, kappa_ci_h = bootstrap_ci(partial(cohen_kappa_score, weights='quadratic'),
                                                                     gt[ind_take, 0], kl_preds,
                                                                     args.n_bootstrap, seed=args.seed)

                        print(f'{np.round(f1_weighted, args.precision)} '
                              f'[{np.round(f1_ci_l, args.precision)}-{np.round(f1_ci_h, args.precision)}] & '
                              f'{np.round(mse, args.precision)} '
                              f'[{np.round(mse_ci_l, args.precision)}-{np.round(mse_ci_h, args.precision)}] & '
                              f'{np.round(acc, args.precision)} '
                              f'[{np.round(acc_ci_l, args.precision)}-{np.round(acc_ci_h, args.precision)}]  & '
                              f'{np.round(kappa, args.precision)} '
                              f'[{np.round(kappa_ci_l, args.precision)}-{np.round(kappa_ci_h, args.precision)}] \\\\')

                        for feature_id, feature_name in enumerate(features):
                            feature_pred = predicts_oarsi[ind_take, feature_id, :].argmax(1)
                            plot_confusion(gt[ind_take, feature_id+1].astype(int), feature_pred,
                                           os.path.join(args.save_dir, f'conf_{feature_name}.pdf'), font=20)

                            clf_rep = classification_report(gt[ind_take, feature_id+1],
                                                            feature_pred,
                                                            digits=args.precision)

                            f1_weighted, f1_ci_l, f1_ci_h = bootstrap_ci(
                                partial(calc_f1_weighted, digits=args.precision),
                                gt[ind_take, feature_id+1],
                                feature_pred,
                                args.n_bootstrap, seed=args.seed)

                            mse, mse_ci_l, mse_ci_h = bootstrap_ci(mean_squared_error,
                                                                   gt[ind_take, feature_id + 1],
                                                                   feature_pred,
                                                                   args.n_bootstrap, seed=args.seed)

                            acc, acc_ci_l, acc_ci_h = bootstrap_ci(balanced_accuracy_score,
                                                                   gt[ind_take, feature_id + 1],
                                                                   feature_pred,
                                                                   args.n_bootstrap, seed=args.seed)

                            kappa, kappa_ci_l, kappa_ci_h = bootstrap_ci(
                                partial(cohen_kappa_score, weights='quadratic'),
                                gt[ind_take, feature_id+1],
                                feature_pred,
                                args.n_bootstrap, seed=args.seed)

                            print(f'=======> ' + feature_name)

                            print(f'{np.round(f1_weighted, args.precision)} '
                                  f'[{np.round(f1_ci_l, args.precision)}-{np.round(f1_ci_h, args.precision)}] & '
                                  f'{np.round(mse, args.precision)} '
                                  f'[{np.round(mse_ci_l, args.precision)}-{np.round(mse_ci_h, args.precision)}] & '
                                  f'{np.round(acc, args.precision)} '
                                  f'[{np.round(acc_ci_l, args.precision)}-{np.round(acc_ci_h, args.precision)}]  & '
                                  f'{np.round(kappa, args.precision)} '
                                  f'[{np.round(kappa_ci_l, args.precision)}-{np.round(kappa_ci_h, args.precision)}'
                                  f']\\\\')
