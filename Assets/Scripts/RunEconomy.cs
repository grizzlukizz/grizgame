using System;

namespace Zone04
{
    internal sealed class RunEconomy
    {
        public const int PowerPrice = 550;
        public const int MaxTier = 3;
        private readonly int[] tiers;
        public int Points { get; private set; } = 350;
        public bool Powered { get; private set; }

        public RunEconomy(int weapons)
        {
            tiers = new int[weapons];
        }

        public void Credit(int amount)
        {
            if(amount>0)
                Points += Math.Min(amount,int.MaxValue-Points);
        }

        public bool TrySpend(int amount)
        {
            if(amount<=0 || amount>Points) return false;
            Points-=amount;
            return true;
        }

        public int Tier(int weapon) => tiers[weapon];

        public int UpgradePrice(int weapon) => 950+tiers[weapon]*650;

        public bool TryPower()
        {
            if(Powered || !TrySpend(PowerPrice)) return false;
            Powered=true;
            return true;
        }

        public bool TryUpgrade(int weapon)
        {
            if(!Powered || tiers[weapon]>=MaxTier || !TrySpend(UpgradePrice(weapon))) return false;
            tiers[weapon]++;
            return true;
        }
    }
}
