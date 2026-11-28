using System;
using UnityEngine;

namespace Zone04
{
    // A clearance-aware, reverse breadth-first search shared by nearby enemies.
    internal sealed class QuarantineNavigation
    {
        private const int Side=75;
        private const float Step=1.23f;
        private static readonly int[] OffsetX={-1,1,0,0};
        private static readonly int[] OffsetY={0,0,-1,1};
        private readonly bool[] open=new bool[Side*Side];
        private readonly byte[] links=new byte[Side*Side];
        private readonly int[] distance=new int[Side*Side];
        private readonly int[] pending=new int[Side*Side];
        private readonly QuarantineMap map;
        private int lastGoal=-1;

        internal QuarantineNavigation(QuarantineMap map,float margin)
        {
            this.map=map;
            for(int cell=0;cell<open.Length;cell++)
                open[cell]=!map.Blocked(Center(cell),margin);
            for(int cell=0;cell<open.Length;cell++)
            {
                if(!open[cell]) continue;
                Vector2 here=Center(cell);
                for(int i=0;i<4;i++)
                {
                    int neighbor=Index(cell%Side+OffsetX[i],cell/Side+OffsetY[i]);
                    if(neighbor>=0 && open[neighbor] && map.FirstCover(here,Center(neighbor),margin)>=1)
                        links[cell]|=(byte)(1<<i);
                }
            }
        }

        private static Vector2 Center(int cell) =>
            new((cell%Side-(Side-1)/2)*Step,(cell/Side-(Side-1)/2)*Step);

        private static int Index(int x,int y) =>
            x>=0 && y>=0 && x<Side && y<Side ? y*Side+x : -1;

        private int Nearest(Vector2 point,bool reachable,float clearance)
        {
            int x=Mathf.RoundToInt(point.x/Step)+(Side-1)/2;
            int y=Mathf.RoundToInt(point.y/Step)+(Side-1)/2;
            int chosen=-1;
            float score=float.PositiveInfinity;
            for(int row=-2;row<=2;row++)
            for(int col=-2;col<=2;col++)
            {
                int cell=Index(x+col,y+row);
                if(cell<0 || !open[cell] || (reachable && distance[cell]<0)) continue;
                Vector2 target=Center(cell);
                float gap=(target-point).sqrMagnitude;
                if(reachable && gap<.025f) continue;
                float cost=gap+(reachable?distance[cell]*7:0);
                if(cost>=score || map.FirstCover(point,target,clearance)<1) continue;
                chosen=cell;
                score=cost;
            }
            return chosen;
        }

        private void UpdateGoal(int goal)
        {
            if(lastGoal==goal) return;
            lastGoal=goal;
            Array.Fill(distance,-1);
            int read=0,write=0;
            pending[write++]=goal;
            distance[goal]=0;
            while(read<write)
            {
                int cell=pending[read++];
                for(int i=0;i<4;i++)
                {
                    if((links[cell] & (1<<i))==0) continue;
                    int next=Index(cell%Side+OffsetX[i],cell/Side+OffsetY[i]);
                    if(distance[next]>=0) continue;
                    distance[next]=distance[cell]+1;
                    pending[write++]=next;
                }
            }
        }

        public bool TryGuide(Vector2 start,Vector2 target,float radius,out Vector2 waypoint)
        {
            waypoint=target;
            int goal=Nearest(target,false,.36f);
            if(goal<0) return false;
            UpdateGoal(goal);
            int cell=Nearest(start,true,radius);
            if(cell<0) return false;
            waypoint=Center(cell);
            return true;
        }
    }
}
