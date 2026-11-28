using System;

namespace Zone04
{
    internal sealed class ExtractionMission
    {
        public const int RequiredWaves=5;
        public const float RequiredSeconds=16;
        public bool Open { get; private set; }
        public bool Complete => Remaining<=0;
        public float Remaining { get; private set; }=RequiredSeconds;

        public bool OpenAfter(int wave,int pending,int enemies)
        {
            if(Open || wave<RequiredWaves || pending>0 || enemies>0) return false;
            Open=true;
            return true;
        }

        public void Advance(float seconds,bool inZone)
        {
            if(Open && inZone && seconds>0)
                Remaining=Math.Max(0,Remaining-seconds);
        }
    }
}
