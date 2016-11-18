from src.utils import *
from src.model_talk_topics import get_talk_doc, tokenize_talk_doc
from src.model_talk_topics import get_topics_from_tf, get_topic_score_names

token_mapper, mdl_LDA = load_lda_model_data()
TK_topics_LDA, TP_info_LDA = load_lda_topics_data()
G_rtopics, U_tscores, U_ftalks = load_group_data()
TK_ratings, TK_info = load_talk_data()

def get_new_user_fav_ratings():
  input_rtyp_idx = get_user_rating_types()

  rtyp_combs = input_rtyp_idx
  for comb_len in xrange(2, len(input_rtyp_idx)+1):
    cur_combs = list(combinations(input_rtyp_idx, comb_len))
    rtyp_combs = rtyp_combs + cur_combs

  U_fratings = []
  for rcomb in rtyp_combs:
    U_fratings.append(get_fratings_per_rtypes(rcomb))

  U_fratings = pd.DataFrame(U_fratings, columns=RATING_TYPES)
  return U_fratings

def get_user_rating_types():
  rtyp_idx = range(len(RATING_TYPES) )
  rtyp_dict = dict(zip(rtyp_idx, RATING_TYPES) )

  for (idx, rtyp) in rtyp_dict.iteritems():
      print '{}: {}'.format(idx, rtyp)

  input_rtyp_idx = raw_input('\nTypes you are interested in: ' + \
    '(say, \'4,5\' for \'Funny+Informative\'):  ')
  if input_rtyp_idx == '':
    input_rtyp_idx = '4,5'
  input_rtyp_idx = map(int, input_rtyp_idx.replace(' ', '').split(','))
  print ', '.join([rtyp_dict[x] for x in input_rtyp_idx])

  return input_rtyp_idx

def get_fratings_per_rtypes(rcomb):
  U_frating = np.repeat(0., len(RATING_TYPES))

  if isinstance(rcomb, int):
    U_frating[rcomb] = 1.
  else:
    for ridx in rcomb:
      U_frating[ridx] = 1. / len(rcomb)

  return U_frating

def get_user_topic_keywords():
  user_text = raw_input('\nTopics you are interested in: (say, \'data science, finance\'):  ')
  if user_text == '':
    user_text = 'data science, technology, computer, economics, finance, market, investing'
  print user_text

  return user_text

def get_topics_from_text_LDA(text):
  tknizer = RegexpTokenizer(r'\w+')
  stop_wds = get_stop_words('en')
  pstemmer = PorterStemmer()
  new_tokens = tokenize_talk_doc(text, tknizer, stop_wds, pstemmer)

  new_tf = token_mapper.doc2bow(new_tokens)
  topics = get_topics_from_tf(new_tf, mdl_LDA)
  result = pd.Series(topics, index=get_topic_score_names())
  return result

def get_new_user_tscores_fratings():

  ## get user input text and rating preference
  user_text = get_user_topic_keywords()
  user_fratings = get_new_user_fav_ratings()
  
  ## convert the user input text to topic scores
  user_tscores = get_topics_from_text_LDA(user_text)

  return user_tscores, user_fratings

def get_user_rec_talks(tscores, user_fratings):

  gtopics_list = map(int, tscores[N_TOTAL_TOPICS:])
  gtopics_key = str(sorted(map(int, tscores[N_TOTAL_TOPICS:])))

  ## for topics to go deeper (topics already liked)
  deeper_rtopics = ['topic{:02d}'.format(x) for x in gtopics_list]
  deeper_candidates = TP_info_LDA.ix[deeper_rtopics, 'tids'].tolist()
  deeper_rtalks = get_rtalks_from_ratings(user_fratings, deeper_candidates)

  ## for topics to go wider (topics new to the user)
  wider_rtopics = G_rtopics[gtopics_key]
  wider_candidates = TP_info_LDA.ix[wider_rtopics, 'tids'].tolist()
  wider_rtalks = get_rtalks_from_ratings(user_fratings, wider_candidates)

  return deeper_rtalks + wider_rtalks, deeper_rtopics + wider_rtopics
 
def get_rtalks_from_ratings(user_ratings, candidates):
  rtalks = []
  for rtt in candidates:
    tratings = TK_ratings.ix[rtt,:]
    rtalks.append( get_closest_rtalk(tratings, user_ratings) )
  return rtalks

def get_closest_rtalk(talk_ratings, fav_ratings, OPTION=['MEAN_DIST', 'MIN_DIST'][1]):
  fr = fav_ratings.values
  dists = {}
  for (tid, tr) in zip(talk_ratings.index, talk_ratings.values):
    dists_to_each_fr = np.sum( (tr-fr)**2, axis=1)
    if OPTION=='MEAN_DIST':
      dists[tid] = dists_to_each_fr.mean()
    elif OPTION=='MIN_DIST':
      dists[tid] = dists_to_each_fr.min()

  rtalk = sorted(dists, key=dists.get)[0]
  return rtalk


def get_existing_user_tscores_fratings(uid):
  user_tscores = U_tscores.ix[uid,:]

  ## NEED_CHECKING: should move to model_user_groups.py?
  top_topics = user_tscores.argsort()[::-1][:N_GROUP_TOPICS] 
  for idx in xrange(N_GROUP_TOPICS):
    user_tscores['top_topic{}'.format(idx+1)] = top_topics[idx]
  
  tids = U_ftalks.ix[U_ftalks.uid_idiap==uid, 'tid']
  user_fratings = TK_ratings.ix[tids]

  return user_tscores, user_fratings


def rec_talks(uid):
  if uid.lower() =='n':
    tscores, fratings = get_new_user_tscores_fratings()
  else:
    if uid.lower() == 'e':
      uid = random.choice( U_tscores.index )
    tscores, fratings = get_existing_user_tscores_fratings(uid)

  rec_tids, rec_topics = get_user_rec_talks(tscores, fratings)
  print_rtalks(rec_tids)


def print_rtalks(rec_tids):
  LINE_LENGTH = 80

  for rtid in rec_tids:
    tt = TK_info.ix[rtid]

    tthemes = tt.related_themes
    msg = '\n====={}: {} ({})=====\n{}\n[keywords]\n{}'.format(\
        tt.speaker, tt.title, tt.ted_event, #rtid,
        textwrap.fill(tt.description, LINE_LENGTH), \
        textwrap.fill(tt.keywords.replace('[','').replace(']',''), LINE_LENGTH))
    if not isinstance(tthemes, float):
      msg = '{}\n[themes]\n{}'.format(msg, 
        re.sub('\[|\]|u\'|\'|\"|u\"', '', tthemes))

    print msg

def evaluate_tids():
  #nftalks_per_user = U_ftalks[['uid_idiap', 'tid']].groupby('uid_idiap').count()
  #uids = nftalks_per_user.ix[nftalks_per_user['tid']>3]
  #uids = np.random.choice(uids.index, size=100)
  return uids

def get_success_metrics(test_udf):
  np.random.seed(319)
  talks_per_topic_LDA = TK_topics_LDA['top_topic1'].value_counts()
  talks_per_topic_LDA = talks_per_topic_LDA.sort_index() / sum(talks_per_topic_LDA)

  deeper_scores, wider_scores, deeper_bmk, wider_bmk = [], [], [], []

  for uid in test_udf['uid_idiap'].unique().tolist():
    tids = test_udf.ix[test_udf['uid_idiap']==uid, 'tid'] 
    tids_input = np.random.choice(tids, 2)
    tids_truth = tids[~tids.isin(tids_input)]

    ## stop here program can't run get_talk_doc()
    user_text = TK_info.ix[tids_input].apply(get_talk_doc, axis=1).tolist()
    user_text = reduce(lambda x, y: x+y, user_text)
    user_text = user_text.replace('[', '').replace(']', '')
    user_tscores = get_topics_from_text_LDA(user_text)

    user_fratings = TK_ratings.ix[tids_input]

    rec_tids, topics_rec = get_user_rec_talks(user_tscores, user_fratings)
    topics_input = TK_topics_LDA.ix[tids_input, 'top_topic1']
    topics_truth = TK_topics_LDA.ix[tids_truth, 'top_topic1']

    topics_rec_num = [float(x.replace('topic0', '')) for x in topics_rec]
    deeper_scores.append(np.mean(topics_truth.isin(topics_rec_num[:N_GROUP_TOPICS]) ))
    wider_scores.append(np.mean(topics_truth.isin(topics_rec_num[N_GROUP_TOPICS:]) ))
    deeper_bmk.append(sum( talks_per_topic_LDA[topics_rec_num[:N_GROUP_TOPICS]] ))
    wider_bmk.append(sum( talks_per_topic_LDA[topics_rec_num[N_GROUP_TOPICS:]] ))
  
  return np.array(deeper_scores), np.array(wider_scores), \
    np.array(deeper_bmk), np.array(wider_bmk)

def evaluate_recommender():
  ## get testing uids
  #uids = evaluate_tids()
  test_udf = pd.read_csv(TEST_USER_TALK_FN)
  test_udf['tid'] = test_udf['tid'].astype(int)
    
  deeper_scores, wider_scores, deeper_bmk, wider_bmk = get_success_metrics(test_udf)
  rec_scores = deeper_scores + wider_scores
  bmk_scores = deeper_bmk + wider_bmk
  outperform_scores = (rec_scores - bmk_scores)

  print 'My recommender: deeper {:4f}, wider {:4f}, total {:4f}'.format(\
    np.mean(deeper_scores), np.mean(wider_scores), np.mean(rec_scores))
  print 'Benchmark: deeper {:4f}, wider {:4f}, total {:4f}'.format(\
    np.mean(deeper_bmk), np.mean(wider_bmk), np.mean(bmk_scores))
  print 'outputform: score {:.4f}, freq {:4f}, pvalue {:4f}'.format(\
    np.mean(outperform_scores), np.mean(outperform_scores>0),
    ttest_1samp(outperform_scores, 0).pvalue)

  return deeper_scores, wider_scores, deeper_bmk, wider_bmk, outperform_scores

  
if __name__ == '__main__':
  MODE = ['RECOMMEND', 'EVALUATE'][1] ##FIXME: to change to EVALUATE

  if MODE == 'RECOMMEND':
    msg = '\nPlease enter your UserID, or "n" (for a new user), or "q" (for quit): '

    uid = raw_input(msg)
    while uid.lower() not in ['q', '']:
      rec_talks(uid)
      uid = raw_input(msg)
  else:
    evaluate_recommender()



