import theano
from theano.tensor import basic as T
from theano.sandbox.cuda import cuda_available, cuda_enabled
#from util import strutil
import numpy as N

class ConvGrad3D(theano.Op):
    """ Gradient of Conv3D with respect to W """
    def __eq__(self,other):
        return type(self) == type(other)

    def __hash__(self):
        return hash(type(self))

    def make_node(self, V, d, WShape, dCdH):
        V_ = T.as_tensor_variable(V)
        d_ = T.as_tensor_variable(d)
        WShape_ = T.as_tensor_variable(WShape)
        dCdH_ = T.as_tensor_variable(dCdH)

        return theano.Apply(self, inputs=[V_, d_, WShape_, dCdH_], outputs = [ T.TensorType(V_.dtype, (False,False,False,False,False))() ] )

    def infer_shape(self, node, input_shapes):
        V,d,W_shape, dCdH = node.inputs
        return [ ( W_shape[0], W_shape[1], W_shape[2], W_shape[3], W_shape[4] ) ]

    def grad(self,inputs, output_gradients):
        C,d, WShape, B = inputs
        dLdA ,= output_gradients

        z = T.zeros_like(C[0,0,0,0,:])
        dLdC = convTransp3D( dLdA, z, d, B, C.shape[1:4])
        dLdd = None #not differentiable, since d is not continuous
        dLdWShape = None #not differentiable, since d is not continuous
        dLdB = conv3D( C, dLdA, T.zeros_like(B[0,0,0,0,:]), d)
        
        return [ dLdC, dLdd, dLdWShape, dLdB ]

    def perform(self, node, inputs, output_storage):
        V, d, WShape, dCdH = inputs
        print "ConvGradW3D python code"

        #partial C / partial W[j,z,k,l,m] = sum_i sum_p sum_q sum_r (partial C /partial H[i,j,p,q,r] ) *  V[i,z,dr*p+k,dc*q+l,dt*r+m] 

        batchSize = dCdH.shape[0]
        outputFilters = dCdH.shape[4]
        outputHeight = dCdH.shape[1]
        outputWidth = dCdH.shape[2]
        outputDur = dCdH.shape[3]
        assert V.shape[0] == batchSize
        inputFilters = V.shape[4]
        inputHeight = V.shape[1]
        inputWidth = V.shape[2]
        inputDur = V.shape[3]
        dr, dc, dt = d

        dCdW = N.zeros(WShape, dtype=V.dtype)

        #print 'computing output of shape '+str(WShape)



        for k in xrange(0,WShape[1]):
            for l in xrange(0,WShape[2]):
                for m in xrange(0,WShape[3]):
                    for i in xrange(0,batchSize):
                        for p in xrange(0,outputHeight):
                            for q in xrange(0,outputWidth):
                                for r in xrange(0,outputDur):
                                    for j in xrange(0,WShape[0]):
                                        for z in xrange(0,WShape[4]):
                                            dCdW[j,k,l,m,z] +=  dCdH[i,p,q,r,j] * V[i,dr*p+k,dc*q+l,dt*r+m,z]

        output_storage[0][0] = dCdW

    def c_compile_args(self):
        flags = ['-Werror']
        return flags

    def c_code(self, node, nodename, (V,d,WShape,dCdH), outputs, sub):
        fail = sub['fail']

        dCdW = outputs[0]

        codeSource =  """          
            ///////////// < code generated by ConvGradW3D >

            //printf("\t\t\t\tConvGradW3D c code\\n");

            //Check dimensionality of inputs
            if (%(dCdH)s->nd != 5)
            {
                PyErr_Format(PyExc_ValueError, "ConvGrad3D: dCdH must be a 5 dimensional tensor"); 
                            %(fail)s
            }

            if (%(V)s->nd != 5)
            {
                PyErr_Format(PyExc_ValueError, "ConvGrad3D: V must be a 5 dimensional tensor"); 
                %(fail)s
            }

            if (%(WShape)s->nd != 1)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: WShape must be a vector.");
                %(fail)s
            }

            if (%(d)s->nd != 1)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: d must be a vector.");
                %(fail)s
            }

            if (%(d)s->dimensions[0] != 3)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: 3 stride length arguments expected (row, col, time) but %%li were given",%(d)s->dimensions[0]);
                %(fail)s
            }
{ //extra scope so that fail will not jump over declarations

            //Read and check sizes of inputs
            const int batchSize = %(V)s->dimensions[0];
            if (%(WShape)s->dimensions[0] != 5)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: WShape must specify a 5D shape");
                %(fail)s
            }
            if (!PyArray_ISCONTIGUOUS(%(WShape)s))
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: WShape must be contiguous");
                %(fail)s
            }
  
{ //extra scope so that fail will not jump over declarations
            dtype_%(WShape)s * WShape = (dtype_%(WShape)s *) %(WShape)s->data;
            const int outputChannels =  WShape[0];
            const int inputChannels = %(V)s->dimensions[4];
            if (WShape[4] != inputChannels)
            {
                PyErr_Format(PyExc_ValueError, "ConvGrad3D: W operates on a %%i channel image but the image has %%i channels",(int) WShape[1],inputChannels); 
                %(fail)s
              
            }
{ //extra scope so fail works
            const int filterHeight = WShape[1];
            const int filterWidth = WShape[2];
            const int filterDur = WShape[3];
            const int vidHeight = %(V)s->dimensions[1];
            const int vidWidth = %(V)s->dimensions[2];
            const int vidDur = %(V)s->dimensions[3];
            if (vidHeight < filterHeight)
            {
                PyErr_Format(PyExc_ValueError, "ConvGrad3D: W has a height of %%i but V is only %%i pixels tall", filterHeight, vidHeight);
                %(fail)s
            }
            if (vidWidth < filterWidth)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: W has a width of %%i but V is only %%i pixels tall",filterWidth,vidWidth);
                %(fail)s
            }
            if (vidDur < filterDur)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: W has a duration of %%i but V is only %%i pixels long",filterDur,vidDur);
                %(fail)s
            }

{ // extra scope so fail works
            //Read and check stride arguments
            const int dr = *(dtype_%(d)s*)PyArray_GETPTR1(%(d)s,0);
            const int dc = *(dtype_%(d)s*)PyArray_GETPTR1(%(d)s,1);
            const int dt = *(dtype_%(d)s*)PyArray_GETPTR1(%(d)s,2);
            if (dr <= 0 || dc <= 0 || dt <= 0)
            {
                PyErr_Format(PyExc_ValueError,"ConvGrad3D: Strides should all be positive but they are %%i, %%i, %%i",dr,dc,dt);
                %(fail)s
            }

{ // extra scope so fail works
            //Compute correct sized of output
            const int outputHeight = int( (vidHeight - filterHeight) / dr )+1;
            const int outputWidth = int( (vidWidth - filterWidth) / dc )+1;
            const int outputDur = int( (vidDur - filterDur) / dt ) +1;



            if (%(dCdH)s->dimensions[0] != batchSize || 
                %(dCdH)s->dimensions[4] != outputChannels ||
                %(dCdH)s->dimensions[1] != outputHeight ||
                %(dCdH)s->dimensions[2] != outputWidth ||
                %(dCdH)s->dimensions[3] != outputDur)
            {
                PyErr_Format(PyExc_ValueError, "dCdH is the wrong size, expected (%%i,%%i,%%i,%%i,%%i), got (%%li,%%li,%%li,%%li,%%li)", batchSize,  outputHeight, outputWidth, outputDur, outputChannels, %(dCdH)s->dimensions[0], %(dCdH)s->dimensions[1], %(dCdH)s->dimensions[2] ,%(dCdH)s->dimensions[3], %(dCdH)s->dimensions[4] );
                %(fail)s
            }
{ // extra scope for fail

            npy_intp dims[5];
            dims[0] = outputChannels;
            dims[4] = inputChannels;
            dims[1] = filterHeight;
            dims[2] = filterWidth;
            dims[3] = filterDur;

            if(!(%(dCdW)s)  || %(dCdW)s->dimensions[0]!=dims[0] || 
                  %(dCdW)s->dimensions[1]!=dims[1] || 
                  %(dCdW)s->dimensions[2]!=dims[2] || 
                  %(dCdW)s->dimensions[3]!=dims[3] || 
                  %(dCdW)s->dimensions[4]!=dims[4] ){
               Py_XDECREF(%(dCdW)s);
               %(dCdW)s = (PyArrayObject *) PyArray_SimpleNew(5, dims, %(V)s->descr->type_num);

               if (!(%(dCdW)s)) {
                  PyErr_Format(PyExc_MemoryError,"ConvGrad3D: Could not allocate dCdW");
                %(fail)s
               }
            }
{ //extra scope so fail works

            #define ELEM5(x, i,j,k,l,m) * ( dtype_ ## x *) ( x->data + (i)*x->strides[0]+(j)*x->strides[1]+(k)*x->strides[2]+(l)*x->strides[3]+(m)*x->strides[4] )

            #define ELEM_AT(x, i) * ( dtype_ ## x *) ( x->data + (i) )

            const int dhs3 = %(dCdH)s->strides[3];
            const int dtvs3 = dt * %(V)s->strides[3];

            // Compute dCdW
            //TODO-- see if this can be made faster by using ELEM_AT instead of ELEM5
            // dCdW[j,k,l,m,z] = sum_i sum_p sum_q sum_r dCdH[i,p,q,r,j]  *  V[i,dr*p+k,dc*q+l,dt*r+m,z]
            for (int j = 0; j < outputChannels; j++) {
                for (int z = 0; z < inputChannels; z++) {
                    for (int k = 0; k < filterHeight; k++) {
                        for (int l = 0; l < filterWidth; l++) {
                            for (int m = 0; m < filterDur; m++) {

                                //printf("writePos %%i %%i %%i %%i %%i \\n",j,k,l,m,z);

                                dtype_%(dCdW)s & writePos =  ELEM5(%(dCdW)s, j,k,l,m,z);
                                writePos = 0;
                                for (int i = 0; i < batchSize; i++) {
                                    for (int p = 0; p < outputHeight; p++) {
                                        for (int q = 0; q < outputWidth; q++) {
                                            int Hpos = i * %(dCdH)s->strides[0] + j * %(dCdH)s->strides[4] + p * %(dCdH)s->strides[1] + q * %(dCdH)s->strides[2] ;
                                            int Vpos = i * %(V)s->strides[0] + z * %(V)s->strides[4] +  (dr * p+k) * %(V)s->strides[1] +  (dc*q+l) * %(V)s->strides[2] + m * %(V)s->strides[3]; 

                                            for (int r = 0; r < outputDur; r++) {    
                                                writePos += ELEM5(%(dCdH)s,i,p,q,r,j) * ELEM5(%(V)s,i,dr*p+k,dc*q+l,dt*r+m,z);
                                                //writePos += ELEM_AT(%(dCdH)s,Hpos) * ELEM_AT(%(V)s,Vpos);
                                                Hpos += dhs3;
                                                Vpos += dtvs3;
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

}}}}}}} // extra scope for fail            
            ///////////// < /code generated by ConvGradW3D >
        """ 

        return strutil.renderString(codeSource,locals()) 


convGrad3D = ConvGrad3D()

from Conv3D import conv3D
from ConvTransp3D import convTransp3D
if cuda_available:
    from theano.sandbox.cuda import CudaNdarrayType, float32_shared_constructor
    from . import GpuConvGrad3D
