"""Reproduce and extend IT-role skill weighting. No raw respondent data are exported.
Run:
  python run_analysis.py --csv survey_results_public.csv --saved weights_v2.csv --out results
  
One command produces every number used in the manuscript, including the revision analyses:
equivalent thresholds (Table II a), within-category denominator invariance, top-10 margin
to the threshold, exact top-10 retention in the bootstrap, and size-matched controls A and B.
The default seeds (2026 bootstrap, 2027 controls) and replicate counts were fixed before
inspecting new estimates. --saved is optional: without it the legacy 228-pair check is skipped.
"""
from fractions import Fraction
from pathlib import Path
import argparse, hashlib, json, itertools, platform, time
import numpy as np
import pandas as pd
import scipy
from scipy import sparse, stats

ROLES = {
    'fullstack': 'Developer, full-stack', 'backend': 'Developer, back-end',
    'frontend': 'Developer, front-end',
    'desktop': 'Developer, desktop or enterprise applications',
    'mobile': 'Developer, mobile', 'ml_engineer': 'AI/ML engineer',
    'embedded': 'Developer, embedded applications or devices',
}
COLUMNS = {'languages':'LanguageHaveWorkedWith','databases':'DatabaseHaveWorkedWith',
           'web':'WebframeHaveWorkedWith','cloud_tools':'PlatformHaveWorkedWith'}
METHODS = ['frequency','ratio','log','sqrt','linear']
THRESHOLDS = [.01,.025,.04,.05,.10]

def scores(freq, baseline):
    ratio=np.divide(freq,baseline,out=np.full_like(freq,np.nan),where=baseline>0)
    return np.column_stack([freq,ratio,freq*np.log1p(ratio),freq*np.sqrt(ratio),freq*ratio])

def corr(a,b):
    if len(a)<2 or np.ptp(a)==0 or np.ptp(b)==0:return np.nan,np.nan
    ra=stats.rankdata(a);rb=stats.rankdata(b)
    return float(np.corrcoef(ra,rb)[0,1]),float(stats.kendalltau(a,b).statistic)

def top(scores_,mask,k):
    ids=np.flatnonzero(mask & np.isfinite(scores_))
    if len(ids)==0:return set()
    cutoff=np.sort(scores_[ids])[::-1][min(k,len(ids))-1]
    return set(ids[scores_[ids]>=cutoff])

def jac(a,b):return len(a&b)/len(a|b) if a|b else np.nan

def membership(values,mask,depths):
    ids=np.flatnonzero(mask & np.isfinite(values)); out=np.zeros((len(depths),len(mask)))
    if len(ids):
        t=stats.rankdata(-values[ids],method='min')
        b=stats.rankdata(-values[ids],method='max')
        out[:,ids]=np.clip((np.asarray(depths)[:,None]-t+1)/(b-t+1),0,1)
    return out

def prefix_b(a,ma,b,mb,persistence=.9):
    """Normalized observed RBO-b component, NOT extrapolated infinite RBO.
    Corsi & Urbano (2024), eqs. 8 and 11. D=min(10,nA,nB).
    Weighted mean of observed depth agreement; disclose D for short lists.
    """
    depth=min(10,int(ma.sum()),int(mb.sum()))
    if depth==0:return np.nan,0
    depths=np.arange(1,depth+1)
    ca=membership(a,ma,depths);cb=membership(b,mb,depths)
    agreement=(ca*cb).sum(1)/np.sqrt((ca*ca).sum(1)*(cb*cb).sum(1))
    weights=(1-persistence)*persistence**(depths-1)
    return float(weights@agreement/weights.sum()),depth

def compare(a,ma,b,mb):
    common=ma&mb&np.isfinite(a)&np.isfinite(b)
    rho,tau=corr(a[common],b[common]);pref,dep=prefix_b(a,ma,b,mb)
    ta=top(a,ma,10);tb=top(b,mb,10)
    return dict(n_a=int(ma.sum()),n_b=int(mb.sum()),n_common=int(common.sum()),
                spearman=rho,kendall=tau,set_jaccard=jac(set(np.flatnonzero(ma)),set(np.flatnonzero(mb))),
                top5_jaccard=jac(top(a,ma,5),top(b,mb,5)),top10_jaccard=jac(ta,tb),
                top10_n_a=len(ta),top10_n_b=len(tb),prefix_b_10=pref,prefix_depth=dep)

def count_rows(X,answered,cats,mask):
    c=np.asarray(X.T@mask.astype(np.float64)).ravel();N=answered[mask].sum(0);M=np.bincount(cats,weights=c,minlength=4)
    return c,N,M

def revision_analyses(args,out,df,X,answered,cats,meta,m,n,complete,role_masks,cache,scopes,boot,strata,cat_names):
    """All analyses added in the revision. Returns a compact summary stored in audit.json."""
    summary={}
    c_all,N_all,M_all=count_rows(X,answered,cats,np.ones(n,bool))
    #(a) Table II a: mean selections per respondent m=M/N and the p threshold equivalent to f>=0.04.
    #Equivalence f>=t <=> c>=t*M <=> p>=t*m is verified with exact integer arithmetic.
    eq_rows=[];mismatch_f=0;mismatch_p=0
    for r,mask in {'all':np.ones(n,bool),**role_masks}.items():
        c,N,M=count_rows(X,answered,cats,mask)
        for j,cat in enumerate(cat_names):
            mk=M[j]/N[j] if N[j] else np.nan
            eq_rows.append(dict(role=r,category=cat,answered=int(N[j]),mentions=int(M[j]),mean_selections_m=mk,
                                p_threshold_equiv_f004=.04*mk))
        for t in THRESHOLDS:
            tf=Fraction(str(t))
            exact=np.array([c[k]*tf.denominator>=tf.numerator*M[cats[k]] for k in range(m)])
            f_float=c/np.where(M[cats]>0,M[cats],np.nan)>=t
            p_equiv=c/np.where(N[cats]>0,N[cats],np.nan)>=t*(M[cats]/np.where(N[cats]>0,N[cats],np.nan))
            mismatch_f+=int((exact!=f_float).sum());mismatch_p+=int((exact!=p_equiv).sum())
    pd.DataFrame(eq_rows).to_csv(out/'equivalent_thresholds.csv',index=False)
    #Boundary cases where floating-point comparison disagrees with the exact integer rule.
    #The manuscript states the equivalence with exact counts; non-zero values show why.
    summary['float_vs_exact_mismatches_f_rule']=mismatch_f
    summary['float_vs_exact_mismatches_p_equivalent_rule']=mismatch_p
    #(b) Within-category invariance: on the fixed p>=0.04 set, f-based scores of frequency, ratio,
    #root and linear are positive rescalings of p-based scores; only log can reorder.
    inv_rows=[]
    for r in role_masks:
        sp=cache[('full',r,'p','inclusive')];sf=cache[('full',r,'f','inclusive')]
        for scope,scope_mask in scopes.items():
            keep=(sp[:,0]>=.04)&scope_mask
            for j,method in enumerate(METHODS):
                a=sp[keep,j];b=sf[keep,j];rho,tau=corr(a,b)
                #compare ranks after rounding to 12 significant digits to ignore floating-point noise
                ra=stats.rankdata(np.round(a/np.max(a),12)) if len(a) else a
                rb=stats.rankdata(np.round(b/np.max(b),12)) if len(b) else b
                identical=bool(len(a)>0 and np.array_equal(ra,rb))
                inv_rows.append(dict(role=r,scope=scope,method=method,n=int(keep.sum()),spearman_p_vs_f=rho,kendall_p_vs_f=tau,ranks_identical=identical))
    inv=pd.DataFrame(inv_rows);inv.to_csv(out/'denominator_within_category.csv',index=False)
    within=inv[inv.scope!='all_categories']
    summary['within_category_min_spearman_log']=float(within[within.method=='log'].spearman_p_vs_f.min())
    summary['within_category_nonlog_all_identical']=bool(within[within.method!='log'].ranks_identical.all())
    #(c) Margin to the threshold: minimum p among the top-10 of the unthresholded ranking.
    margin_rows=[]
    for r in role_masks:
        sc=cache[('full',r,'p','inclusive')]
        for scope,scope_mask in scopes.items():
            valid=scope_mask&(sc[:,0]>0)
            for j,method in enumerate(METHODS):
                ids=list(top(sc[:,j],valid,10))
                mp=float(sc[ids,0].min()) if ids else np.nan
                margin_rows.append(dict(role=r,scope=scope,method=method,top10_size=len(ids),min_p_in_top10=mp,
                                        unchanged_on_grid_guaranteed=bool(mp>=max(THRESHOLDS))))
    pd.DataFrame(margin_rows).to_csv(out/'top10_threshold_margin.csv',index=False)
    # (d) Exact top-10 retention in the bootstrap (tie-expanded set identical, order ignored).
    ret_rows=[]
    for (r,scope,method),g in boot.groupby(['role','scope','method'],sort=False):
        v=g.top10_jaccard.dropna().to_numpy();B=len(v)
        share=float(np.isclose(v,1).mean()) if B else np.nan
        ret_rows.append(dict(role=r,scope=scope,method=method,valid_replicates=B,exact_top10_retention=share,
                             mc_se_retention=float(np.sqrt(share*(1-share)/B)) if B else np.nan,
                             mean_top10_jaccard=float(v.mean()) if B else np.nan,
                             mc_se_mean_jaccard=float(v.std(ddof=1)/np.sqrt(B)) if B>1 else np.nan))
    ret=pd.DataFrame(ret_rows);ret.to_csv(out/'bootstrap_top10_retention.csv',index=False)
    summary['backend_pooled_retention']={k:float(v) for k,v in ret[(ret.role=='backend')&(ret.scope=='all_categories')].set_index('method').exact_top10_retention.items()}
    #(e) Size-matched controls. Reference = full-file ranking; observed = complete-answer cohort.
    rng=np.random.default_rng(args.control_seed)
    devtype=df.DevType.fillna('__MISSING__').to_numpy()
    strata_ids=[ids for ids in strata]
    target=[int(complete[ids].sum()) for ids in strata_ids]
    ctrl_methods=[0,1,2]  # p, L, log
    def evaluate(design,rep,sc_by_role,scopes_used):
        rows=[]
        for r in role_masks:
            ref=cache[('full',r,'p','inclusive')];sc=sc_by_role[r]
            for scope in scopes_used:
                sm=scopes[scope];ma=(ref[:,0]>=.04)&sm;mb=(sc[:,0]>=.04)&sm
                for j in ctrl_methods:
                    res=compare(ref[:,j],ma,sc[:,j],mb)
                    rows.append(dict(design=design,replicate=rep,role=r,scope=scope,method=METHODS[j],
                                     spearman=res['spearman'],top10_jaccard=res['top10_jaccard'],n_selected=res['n_b']))
        return rows
    observed=evaluate('observed_complete',-1,{r:cache[('complete',r,'p','inclusive')] for r in role_masks},list(scopes))
    ctrl_rows=[]
    within_scopes=[c for c in cat_names]
    for rep in range(args.controls):
        #Control A: same number of records per DevType stratum as the complete cohort, from the full file.
        pick=np.concatenate([rng.choice(ids,size=k,replace=False) for ids,k in zip(strata_ids,target) if k>0])
        mask=np.zeros(n,bool);mask[pick]=True
        ca,Na,_=count_rows(X,answered,cats,mask);base=ca/np.where(Na[cats]>0,Na[cats],np.nan)
        sc_by={}
        for r,rm in role_masks.items():
            c,N,_=count_rows(X,answered,cats,mask&rm)
            sc_by[r]=scores(c/np.where(N[cats]>0,N[cats],np.nan),base)
        ctrl_rows+=evaluate('control_A_records',rep,sc_by,list(scopes))
        #Control B: per question, among valid answerers, exact complete-cohort count per stratum.
        sc_by={r:np.full((m,5),np.nan) for r in role_masks}
        for j,cat in enumerate(cat_names):
            cols=cats==j;maskq=np.zeros(n,bool)
            for ids,k in zip(strata_ids,target):
                if k==0:continue
                pool=ids[answered[ids,j]]
                maskq[rng.choice(pool,size=k,replace=False)]=True
            cq=np.asarray(X.T@maskq.astype(np.float64)).ravel()[cols];Nq=answered[maskq,j].sum()
            base=cq/Nq
            for r,rm in role_masks.items():
                cr=np.asarray(X.T@(maskq&rm).astype(np.float64)).ravel()[cols];Nr=answered[maskq&rm,j].sum()
                sc_by[r][cols]=scores(cr/Nr if Nr else np.full(cols.sum(),np.nan),base)
        ctrl_rows+=evaluate('control_B_answerers',rep,sc_by,within_scopes)
        if (rep+1)%50==0:print(f'CONTROLS {rep+1}/{args.controls}',flush=True)
    ctrl=pd.DataFrame(ctrl_rows);ctrl.to_csv(out/'control_replicates.csv.gz',index=False,compression='gzip')
    obs=pd.DataFrame(observed).set_index(['role','scope','method'])
    comp_rows=[]
    for (design,r,scope,method),g in ctrl.groupby(['design','role','scope','method'],sort=False):
        o=obs.loc[(r,scope,method)]
        row=dict(design=design,role=r,scope=scope,method=method,valid_replicates=int(g.spearman.notna().sum()),
                 observed_spearman=o.spearman,observed_top10_jaccard=o.top10_jaccard)
        for metric in ['spearman','top10_jaccard']:
            v=g[metric].dropna().to_numpy()
            row[metric+'_median']=float(np.median(v)) if len(v) else np.nan
            row[metric+'_lower']=float(np.quantile(v,.025)) if len(v) else np.nan
            row[metric+'_upper']=float(np.quantile(v,.975)) if len(v) else np.nan
            #share of controls at or below the observed agreement (small = unusually low agreement)
            row[metric+'_share_le_observed']=float((v<=o[metric]+1e-12).mean()) if len(v) and np.isfinite(o[metric]) else np.nan
        comp_rows.append(row)
    pd.DataFrame(comp_rows).to_csv(out/'control_comparison.csv',index=False)
    summary['controls']={'stratum_targets_total':int(sum(target)),'replicates':args.controls}
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--csv',required=True)
    parser.add_argument('--saved',default=None);parser.add_argument('--out',default='results')
    parser.add_argument('--bootstrap',type=int,default=1000);parser.add_argument('--seed',type=int,default=2026)
    parser.add_argument('--controls',type=int,default=1000);parser.add_argument('--control-seed',type=int,default=2027)
    args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(args.csv,low_memory=False);n=len(df)
    audit={'csv_sha256':hashlib.sha256(Path(args.csv).read_bytes()).hexdigest(),
           'shape':list(df.shape),'duplicate_rows':int(df.duplicated().sum()),
           'response_id_missing':int(df.ResponseId.isna().sum()),'response_id_unique':int(df.ResponseId.nunique()),
           'devtype_missing':int(df.DevType.isna().sum()),
           'multivalued_devtype':int(df.DevType.fillna('').str.contains(';',regex=False).sum()),
           'tools_field_present':'ToolsTechHaveWorkedWith' in df,
           'official_website_n':49009,'website_difference':n-49009,
           'website_difference_explanation':'Not established by the available respondent file; no arbitrary row deletion.',
           'versions':dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__),
           'seed':args.seed,'bootstrap_replicates':args.bootstrap,'control_seed':args.control_seed,'control_replicates':args.controls}
    #Binary respondent x technology incidence; retain the questionnaire category.
    meta=[];rr=[];cc=[];answered=[];token_duplicates=0
    for cat,col in COLUMNS.items():
        parsed=df[col].fillna('').map(lambda s:[v.strip() for v in s.split(';') if v.strip()])
        token_duplicates+=sum(len(v)-len(set(v)) for v in parsed)
        vocabulary=sorted(set(itertools.chain.from_iterable(parsed)))
        index={s:len(meta)+i for i,s in enumerate(vocabulary)}
        for s in vocabulary:meta.append({'category':cat,'column':col,'skill':s})
        for i,items in enumerate(parsed):
            for s in set(items):rr.append(i);cc.append(index[s])
        answered.append(parsed.map(bool).to_numpy())
    meta=pd.DataFrame(meta);m=len(meta);cat_names=list(COLUMNS)
    cats=np.array([cat_names.index(c) for c in meta.category]);answered=np.column_stack(answered)
    X=sparse.csr_matrix((np.ones(len(rr),dtype=np.float64),(rr,cc)),shape=(n,m))
    audit['duplicate_tokens_removed']=int(token_duplicates)
    audit['technology_count']=m
    audit['global_answered']={cat:int(answered[:,i].sum()) for i,cat in enumerate(cat_names)}
    role_masks={r:df.DevType.eq(value).to_numpy() for r,value in ROLES.items()}
    audit['exact_vs_substring_roles']={r:bool(np.array_equal(mask,df.DevType.str.contains(ROLES[r],na=False,regex=False).to_numpy())) for r,mask in role_masks.items()}
    complete=answered.all(1);audit['complete_cases']=int(complete.sum())
    respondent_rows=[]
    for r,mask in {'all':np.ones(n,bool),**role_masks}.items():
        row={'role':r,'n_total':int(mask.sum()),'n_complete':int((mask&complete).sum())}
        for j,cat in enumerate(cat_names):row['answered_'+cat]=int(answered[mask,j].sum())
        respondent_rows.append(row)
    pd.DataFrame(respondent_rows).to_csv(out/'respondents.csv',index=False)
    #Reproduce legacy code exactly, including rounding only on export.
    full_c=np.asarray(X.sum(0)).ravel();full_M=np.bincount(cats,weights=full_c,minlength=4)
    old=[]
    for r,mask in role_masks.items():
        c=np.asarray(X[mask].sum(0)).ravel();M=np.bincount(cats,weights=c,minlength=4)
        f=c/M[cats];L=f/(full_c/full_M[cats]);S=f*np.log1p(L);keep=f>=.04
        W=(S[keep]-S[keep].min())/(S[keep].max()-S[keep].min())
        for j,w in zip(np.flatnonzero(keep),W):
            old.append(dict(role=r,skill=meta.skill[j],category=meta.category[j],raw_frequency=round(f[j],3),relative_weight=round(L[j],3),weight_0_1=w,f_full=f[j],L_full=L[j],S_full=S[j]))
    old=pd.DataFrame(old);old.to_csv(out/'legacy_reproduced.csv',index=False)
    if args.saved:
     saved=pd.read_csv(args.saved);survey_saved=saved[saved.relative_weight.notna()]
     joined=old.merge(survey_saved,on=['role','skill'],suffixes=('_calc','_saved'),how='outer',indicator=True)
     audit['legacy']={'computed_pairs':len(old),'saved_survey_pairs':len(survey_saved),
      'key_counts':joined['_merge'].value_counts().astype(int).to_dict(),
      'rounded_frequency_equal':bool((joined.raw_frequency_calc==joined.raw_frequency_saved).all()),
      'rounded_ratio_equal':bool((joined.relative_weight_calc==joined.relative_weight_saved).all()),
      'max_weight_error':float(np.max(np.abs(joined.weight_0_1_calc-joined.weight_0_1_saved)))}
    # Full and common-respondent cohorts, both denominator conventions, both backgrounds.
    cache={};score_rows=[];inventory=[]
    for cohort,cohort_mask in [('full',np.ones(n,bool)),('complete',complete)]:
        c_all=np.asarray(X[cohort_mask].sum(0)).ravel();N_all=answered[cohort_mask].sum(0)
        M_all=np.bincount(cats,weights=c_all,minlength=4)
        for r,r_mask in role_masks.items():
            mask=cohort_mask&r_mask;c=np.asarray(X[mask].sum(0)).ravel();N=answered[mask].sum(0)
            M=np.bincount(cats,weights=c,minlength=4)
            for j in range(m):inventory.append(dict(cohort=cohort,role=r,**meta.iloc[j].to_dict(),count_role=c[j],answered_role=N[cats[j]],mentions_role=M[cats[j]],count_all=c_all[j],answered_all=N_all[cats[j]],mentions_all=M_all[cats[j]]))
            for norm,den,all_den in [('p',N,N_all),('f',M,M_all)]:
                f=c/den[cats]
                for bg in ['inclusive','excluded']:
                    b=c_all/all_den[cats] if bg=='inclusive' else (c_all-c)/(all_den-den)[cats]
                    sc=scores(f,b);cache[(cohort,r,norm,bg)]=sc
                    for j in range(m):
                        score_rows.append(dict(cohort=cohort,role=r,denominator=norm,background=bg,**meta.iloc[j].to_dict(),**dict(zip(METHODS,sc[j]))))
    pd.DataFrame(inventory).to_csv(out/'technology_counts.csv',index=False)
    pd.DataFrame(score_rows).to_csv(out/'scores_full_precision.csv',index=False)
    scopes={'all_categories':np.ones(m,bool),**{c:meta.category.eq(c).to_numpy() for c in cat_names}}
    correlations=[];threshold_rows=[];effects=[];variances=[];top_rows=[]
    for (cohort,r,norm,bg),sc in cache.items():
        for threshold in THRESHOLDS:
            for scope,scope_mask in scopes.items():
                keep=(sc[:,0]>=threshold)&scope_mask
                for a,b in itertools.combinations(range(5),2):
                    rho,tau=corr(sc[keep,a],sc[keep,b])
                    correlations.append(dict(cohort=cohort,role=r,denominator=norm,background=bg,threshold=threshold,scope=scope,n=int(keep.sum()),a=METHODS[a],b=METHODS[b],spearman=rho,kendall=tau))
                if cohort=='full' and bg=='inclusive':
                    ref=(sc[:,0]>=.04)&scope_mask
                    for j,method in enumerate(METHODS):
                        threshold_rows.append(dict(role=r,denominator=norm,threshold=threshold,scope=scope,method=method,**compare(sc[:,j],ref,sc[:,j],keep)))
                if threshold==.04:
                    for j,method in enumerate(METHODS):
                        ids=sorted(top(sc[:,j],keep,5),key=lambda k:(-sc[k,j],meta.skill[k]))
                        for k in ids:top_rows.append(dict(cohort=cohort,role=r,denominator=norm,background=bg,scope=scope,method=method,skill=meta.skill[k],category=meta.category[k],score=sc[k,j],rank_min=int(1+(sc[keep,j]>sc[k,j]).sum()),n=int(keep.sum())))
                    ids=keep&(sc[:,0]>0)&(sc[:,1]>0)&np.isfinite(sc).all(1)
                    if ids.sum()>1:
                        A=np.log(sc[ids,0]);B=np.log(np.log1p(sc[ids,1]));V=np.var(A+B,ddof=1)
                        va=np.var(A,ddof=1);vb=np.var(B,ddof=1);cov=2*np.cov(A,B,ddof=1)[0,1]
                        variances.append(dict(cohort=cohort,role=r,denominator=norm,background=bg,scope=scope,n=int(ids.sum()),var_log_score=V,var_log_frequency=va,var_log_log_ratio=vb,twice_covariance=cov,share_frequency=va/V,share_ratio=vb/V,share_covariance=cov/V,identity_error=V-va-vb-cov))
    for r in ROLES:
        sc=cache[('full',r,'p','inclusive')]
        comparisons=[('denominator_fixed_p_set',cache[('full',r,'f','inclusive')],False),
                     ('denominator_own_sets',cache[('full',r,'f','inclusive')],True),
                     ('background_excluded',cache[('full',r,'p','excluded')],False),
                     ('complete_cases_own_sets',cache[('complete',r,'p','inclusive')],True)]
        for effect,other,own_set in comparisons:
            for scope,scope_mask in scopes.items():
                ma=(sc[:,0]>=.04)&scope_mask;mb=(other[:,0]>=.04)&scope_mask if own_set else ma
                for j,method in enumerate(METHODS):
                    result=dict(effect=effect,role=r,scope=scope,method=method,**compare(sc[:,j],ma,other[:,j],mb))
                    for persistence in [.8,.95]:result['prefix_b_'+str(persistence)]=prefix_b(sc[:,j],ma,other[:,j],mb,persistence)[0]
                    effects.append(result)
    for name,rows in [('method_correlations',correlations),('threshold_sensitivity',threshold_rows),('design_effects',effects),('variance_decomposition',variances),('top5',top_rows)]:pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
    print('AUDIT',json.dumps(audit,ensure_ascii=False),flush=True)
    #Conditional stratified respondent bootstrap. Preserve every DevType stratum size.
    rng=np.random.default_rng(args.seed)
    strata=[np.flatnonzero(df.DevType.fillna('__MISSING__').eq(v).to_numpy()) for v in df.DevType.fillna('__MISSING__').unique()]
    role_X={r:X[mask] for r,mask in role_masks.items()};role_A={r:answered[mask] for r,mask in role_masks.items()}
    metric_rows=[];delta_rows=[];inclusion=np.zeros((len(ROLES),m));top_inclusion=np.zeros((len(ROLES),5,m))
    for start in range(0,args.bootstrap,20):
        batch=min(20,args.bootstrap-start);W=np.zeros((n,batch))
        for ids in strata:
            for b in range(batch):W[ids,b]=rng.multinomial(len(ids),np.full(len(ids),1/len(ids)))
        ca=X.T@W;na=answered.T@W
        for ri,(r,mask) in enumerate(role_masks.items()):
            wr=W[mask];c=role_X[r].T@wr;N=role_A[r].T@wr
            ref=cache[('full',r,'p','inclusive')];ref_keep=ref[:,0]>=.04
            for b in range(batch):
                freq=c[:,b]/N[cats,b];baseline=ca[:,b]/na[cats,b];sc=scores(freq,baseline);keep=freq>=.04
                inclusion[ri]+=keep
                for j in range(5):
                    for k in top(sc[:,j],keep,10):top_inclusion[ri,j,k]+=1
                for scope,scope_mask in scopes.items():
                    ma=ref_keep&scope_mask;mb=keep&scope_mask
                    for j,method in enumerate(METHODS):
                        metric_rows.append(dict(replicate=start+b,role=r,scope=scope,method=method,**compare(ref[:,j],ma,sc[:,j],mb)))
                    # Paired correlation differences, fixed original selected set.
                    for set_rule,valid in [('fixed',ma),('reselected',mb)]:
                        fp=corr(sc[valid,0],sc[valid,2]);lp=corr(sc[valid,1],sc[valid,2])
                        delta_rows.append(dict(replicate=start+b,role=r,scope=scope,set_rule=set_rule,n=int(valid.sum()),spearman_frequency_log=fp[0],spearman_ratio_log=lp[0],spearman_delta=fp[0]-lp[0],kendall_frequency_log=fp[1],kendall_ratio_log=lp[1],kendall_delta=fp[1]-lp[1]))
        print(f'BOOTSTRAP {start+batch}/{args.bootstrap}',flush=True)
    boot=pd.DataFrame(metric_rows);boot.to_csv(out/'bootstrap_metrics.csv.gz',index=False,compression='gzip')
    delta=pd.DataFrame(delta_rows);delta.to_csv(out/'bootstrap_paired_correlations.csv.gz',index=False,compression='gzip')
    summaries=[]
    def summarize(table,keys,metrics,label):
        rows=[]
        for labels,g in table.groupby(keys,sort=False):
            common=dict(zip(keys,labels))
            for metric in metrics:
                values=g[metric].dropna().to_numpy()
                rows.append(dict(**common,metric=metric,valid_replicates=len(values),median=np.median(values) if len(values) else np.nan,lower=np.quantile(values,.025) if len(values) else np.nan,upper=np.quantile(values,.975) if len(values) else np.nan))
        pd.DataFrame(rows).to_csv(out/(label+'.csv'),index=False)
    summarize(boot,['role','scope','method'],['spearman','kendall','set_jaccard','top5_jaccard','top10_jaccard','prefix_b_10','n_common'],'bootstrap_stability_summary')
    summarize(delta,['role','scope','set_rule'],['spearman_frequency_log','spearman_ratio_log','spearman_delta','kendall_frequency_log','kendall_ratio_log','kendall_delta'],'bootstrap_correlation_summary')
    prob=[]
    for ri,r in enumerate(ROLES):
        for j,method in enumerate(METHODS):
            for k in range(m):prob.append(dict(role=r,method=method,**meta.iloc[k].to_dict(),selection_probability=inclusion[ri,k]/args.bootstrap,top10_probability=top_inclusion[ri,j,k]/args.bootstrap))
    pd.DataFrame(prob).to_csv(out/'bootstrap_inclusion_probabilities.csv',index=False)
    #Revision analyses (manuscript sections II B-F)
    revision=revision_analyses(args,out,df,X,answered,cats,meta,m,n,complete,role_masks,cache,scopes,boot,strata,cat_names)
    audit['revision']=revision
    audit['elapsed_note']='All recorded bootstrap statistics recompute role and inclusive global frequencies from the same resampled respondents.'
    (out/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    #Basic mathematical and data checks, rather than tests mirroring a builder.
    assert (X.data==1).all() and audit['duplicate_rows']==0
    assert all(audit['exact_vs_substring_roles'].values())
    if args.saved:
        assert audit['legacy']['key_counts'].get('both')==228
        assert audit['legacy']['rounded_frequency_equal'] and audit['legacy']['rounded_ratio_equal']
        assert audit['legacy']['max_weight_error']<1e-12
    assert max(abs(v['identity_error']) for v in variances)<1e-12
    assert np.isclose(prefix_b(np.array([2.,2.,1.]),np.ones(3,bool),np.array([2.,2.,1.]),np.ones(3,bool))[0],1)
    assert np.isclose(prefix_b(np.array([2.,1.,0.,0.]),np.array([1,1,0,0],bool),np.array([0.,0.,2.,1.]),np.array([0,0,1,1],bool))[0],0)
    assert audit['revision']['within_category_nonlog_all_identical']
    print('COMPLETE',flush=True)

if __name__=='__main__':main()
