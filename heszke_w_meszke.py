from mpi4py import MPI

class Dupa:
    def __init__(self):
        self.ddupa = "ddupa"

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
a = Dupa()
if rank == 0:
    comm.send(a, dest=1)

if rank ==1:
    au = comm.recv(source=0)
    print(au.ddupa)
