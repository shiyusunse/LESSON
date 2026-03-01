python calc_code_bleu.py --refs reference_files --hyp candidate_file --lang java ( or c_sharp) --params 0.25,0.25,0.25,0.25(default)


python calc_code_bleu.py --refs reference_files --hyp candidate_file --lang java ( or c_sharp) --params 0.25,0.25,0.25,0.25(default)


python calc_code_bleu.py --refs reference_files --hyp candidate_file --lang c_sharp


basedir=/data/czwang/zongjie/steal_pl2pl/codetrans/model
python calc_code_bleu.py --refs $basedir/train_IMIcodexCodeTrans_INCON.gold --hyp $basedir/train_IMIcodexCodeTrans_INCON.output --lang c_sharp

python calc_code_bleu.py --refs $basedir/train_IMIcodexCodeTrans_Normal.gold --hyp $basedir/train_IMIcodexCodeTrans_Normal.output --lang c_sharp

