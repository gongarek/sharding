from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

if rank==1:
    comm.send(None, dest=0)
comm.barrier()
if rank==0:
    print(comm.recv(source=1))

