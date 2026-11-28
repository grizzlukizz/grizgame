using System;

namespace Zone04
{
    internal static class CollisionMath
    {
        // Return the first contact fraction, or 1 when the segment has no earlier hit.
        public static float Box(float ax,float ay,float dx,float dy,float left,float bottom,float right,float top)
        {
            float enter=0,exit=1;
            return Slab(ax,dx,left,right,ref enter,ref exit) &&
                   Slab(ay,dy,bottom,top,ref enter,ref exit) ? enter : 1;
        }

        private static bool Slab(float a,float delta,float min,float max,ref float enter,ref float exit)
        {
            if(Math.Abs(delta)<1e-6f) return a>=min && a<=max;
            float x=(min-a)/delta,y=(max-a)/delta;
            enter=Math.Max(enter,Math.Min(x,y));
            exit=Math.Min(exit,Math.Max(x,y));
            return enter<=exit;
        }

        public static float Circle(float x,float y,float dx,float dy,float radius)
        {
            float c=x*x+y*y-radius*radius;
            if(c<=0) return 0;
            float q=dx*dx+dy*dy,dot=x*dx+y*dy;
            float h=dot*dot-q*c;
            if(q<=0 || h<0) return 1;
            float t=(-dot-(float)Math.Sqrt(h))/q;
            return t>=0 && t<1 ? t : 1;
        }
    }
}
