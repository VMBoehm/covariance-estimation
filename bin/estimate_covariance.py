from sklearn.covariance import LedoitWolf, EmpiricalCovariance, OAS
import scipy.linalg as lg
import numpy.linalg as nlg
from sklearn.decomposition import PCA
import os 

def estimate_covariances(d_v,mv_in, mv_out,modes,masks,path):
    for mode in modes:
        for masking in masks:
            for ii, d in enumerate(d_v):
                if masking:
                    filename = os.path.join(path,'cov_estimate_%s_%d_masked.pkl'%(mode,ii))
                else:   
                    filename = os.path.join(path,'cov_estimate_%s_%d.pkl'%(mode,ii)) 
                if not os.path.isfile(filename):
                    cov = CovarianceEstimator(mode=mode,label=ii,masking=masking)
                    cov.fit(d,mv_in[ii],mv_out[ii])
                    cov.diag_decomp()          
                    cov.pca(d,mv_in[ii],mv_out[ii])
                    cov.save(path)
    return True


class CovarianceEstimator():

    def __init__(self,mode, label, masking):
        
        assert(mode in ['ML','OAS', 'LW','NERCOME'])
        self.mode   = mode
        self.label  = label
        self.masking= masking
    
    def diag_decomp(self):
        # do svd for numerical stability (ensuring var>=0)
        U,s,V     = lg.svd(self.cov)
        indices   = np.argsort(s)[::-1]
        self.vars = s[indices]
        self.R    = V[indices]
        if len(np.where(self.vars==0.)[0])>0:
            print('covariance estimate contains singular eigenvalues')
        #print('svd ratio', np.mean(np.dot(np.dot(self.R.T,np.diag(self.vars)),self.R)/self.cov))
        return True
    
    def pca(self,data, mask_in, mask_out):
        
        data = self._data_prep(data, mask_in,mask_out)
        
        num       = data.shape[1]
        pca       = PCA(svd_solver='full',n_components=num)
        pca.fit(data)
        self.pca_vars= pca.explained_variance_
        self.pca_R   = pca.components_
        #print('pca ratio', np.mean(np.dot(np.dot(self.pca_R.T,np.diag(self.pca_vars)),self.pca_R)/self.cov))
        
    def _data_prep(self,data, mask_in, mask_out):
        
        if len(mask_in)==data.shape[1]:
            self.masking = False
            print('no zero variance pixels in data')
        
        if self.masking:
            data = data[:, mask_in]
        else:
            #inpainting white noise
            data[:,mask_out] = np.random.randn(np.prod(data.shape)).reshape(data.shape)[:,mask_out]*0.1
            
        self.mask_in = mask_in
        self.mask_out= mask_out
        self.mean = np.mean(data, axis=0)
        
        return data
    
    
    def dist(self,cov1,cov2=None):
        if np.any(cov2 == None):
            cov2=self.cov
        A = cov1-cov2
        dist = np.trace(np.dot(A,A.T))
        return dist
    
    
    def nercome_estimator(self,data,splits=None,num_esti=None):

        nn      = len(data)
        ddim    = data.shape[1]
        if splits== None:
            if ddim < 200:
                splits = [0.33,0.4,0.45,0.5,0.55,0.66,0.7,0.75,0.8]
            else:
                splits = [0.66]
        if num_esti== None:
            num_esti  = min(nn//2,100)

        minQs      = -1
        best_split = 0.
        best_esti  = np.zeros((ddim,ddim))
        for split_frac in splits:
            print('nercome estimation with split %.2f, #samples %d'%(split_frac,num_esti))
            split    = np.int(split_frac*nn)
            cov      = np.zeros((ddim,ddim))
            cov_esti = np.zeros((ddim,ddim))
            for ii in range(num_esti):
                np.random.shuffle(data)
                data1 = data[0:split]
                data2 = data[split::]
                cov1     = EmpiricalCovariance().fit(data1).covariance_
                w1,v1    = lg.eigh(cov1)
                del cov1, w1
                cov2     = EmpiricalCovariance().fit(data2).covariance_
                diags    = np.diag(np.dot(np.dot(v1.T,cov2),v1))
                esti     = np.dot(np.dot(v1,np.diag(diags)),v1.T)
                cov+=cov2/num_esti
                del cov2
                cov_esti+=esti/num_esti

            Q = self.dist(cov_esti, cov)
            if minQs==-1 or Q<minQs:
                minQs=Q
                best_split=split_frac
                best_esti = cov_esti
 
        return best_esti
        

    def fit(self,data, mask_in, mask_out):
        
        data = self._data_prep(data, mask_in,mask_out)
        
        if self.mode =='ML':
            self.cov = EmpiricalCovariance().fit(data).covariance_
        elif self.mode =='OAS':
            self.cov = OAS().fit(data).covariance_
        elif self.mode =='LW':
            self.cov = LedoitWolf().fit(data).covariance_
        elif self.mode =='NERCOME':
            self.cov = self.nercome_estimator(data)
        else: 
            raise ValueError
            
        return True
    
    def compute_logdet(self):
        #numerically unstable 
        sign ,self.logdetC = nlg.slogdet(self.cov)
        return True

    def compute_inverse(self):
        #full thing is often note invertible, use decomposition
        self.Cinv = lg.inv(self.cov)
        return True
    
    def save(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        if self.masking:
            self.filename = os.path.join(path,'cov_estimate_%s_%d_masked.pkl'%(self.mode,self.label))
        else:   
            self.filename = os.path.join(path,'cov_estimate_%s_%d.pkl'%(self.mode,self.label))
        
        pkl.dump(self, open(self.filename,'wb'))
        
        return self.filename
