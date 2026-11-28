using System.Collections.Generic;
using UnityEngine;

namespace Zone04
{
    public sealed partial class Quarantine
    {
        private enum StationKind { Weapon, Ammo, Medkit, Power, Armor, Mobility, Calibration, Case }

        private sealed class Station
        {
            public StationKind Kind;
            public Vector2 Position;
            public int Weapon;
            public bool RequiresPower;
            public GameObject OnLamp, OffLamp;
        }

        private const int MaxReserve=240;
        private static readonly int[] WeaponPrices={0,600,820,1130,1500,1650};
        private readonly List<Station> stations=new();
        private RunEconomy economy;
        private bool plated, quickHands;

        private void SetupStations()
        {
            economy=new RunEconomy(Weapons.Length);
            plated=quickHands=false;
            stations.Clear();

            AddStation(StationKind.Power,new Vector2(0,-3.1f));
            StationKind[] ring={
                StationKind.Calibration,StationKind.Weapon,StationKind.Ammo,StationKind.Weapon,
                StationKind.Armor,StationKind.Weapon,StationKind.Medkit,StationKind.Weapon,
                StationKind.Mobility,StationKind.Weapon,StationKind.Case
            };
            int stock=1;
            for(int i=0;i<ring.Length;i++)
            {
                float theta=Mathf.PI*2*i/ring.Length;
                Vector2 at=new(Mathf.Sin(theta)*6.8f,Mathf.Cos(theta)*6.8f);
                AddStation(ring[i],at,ring[i]==StationKind.Weapon?stock++:-1);
            }
        }

        private void AddStation(StationKind kind,Vector2 at,int stock=-1)
        {
            Transform stand=Models.Node(arenaContents,"Terminal - "+kind,World(at));
            stand.rotation=Quaternion.Euler(0,Yaw(-at),0);
            string hue=kind switch {
                StationKind.Weapon=>"617E98", StationKind.Ammo=>"B6A262", StationKind.Medkit=>"75A28A",
                StationKind.Power=>"E4B464", StationKind.Armor=>"799BCE", StationKind.Mobility=>"77B6BC",
                StationKind.Calibration=>"967FBF", _=>"BE8765"
            };
            Models.Block(stand,"Foot",new Vector3(0,.08f,0),1.24f,.16f,1.08f,"293B4B");
            Models.Block(stand,"Cabinet",new Vector3(0,.48f,0),1.08f,.75f,.65f,hue);
            Models.Block(stand,"Console",new Vector3(0,.89f,.05f),1.12f,.16f,.75f,"35495E");
            Models.Block(stand,"Front plate",new Vector3(0,.51f,.335f),.58f,.35f,.032f,"25374A");
            if(kind==StationKind.Weapon)
            {
                Transform rack=Models.Node(stand,"Weapon display",new Vector3(0,1.08f,.015f));
                rack.localRotation=Quaternion.Euler(0,90,-10);
                rack.localScale=Vector3.one*.79f;
                ActorModel.BuildWeapon(rack,stock);
            }
            else
            {
                for(int i=-1;i<=1;i++)
                    Models.Block(stand,"Highlight",new Vector3(i*.24f,1.01f,.11f),.152f,.081f,.47f,hue);
            }
            var station=new Station {
                Kind=kind, Position=at, Weapon=stock,
                RequiresPower=kind==StationKind.Armor || kind==StationKind.Mobility ||
                    kind==StationKind.Calibration || kind==StationKind.Case
            };
            if(station.RequiresPower || kind==StationKind.Power)
            {
                station.OnLamp=Models.Block(stand,"Ready lamp",new Vector3(0,1.03f,-.23f),
                    .28f,.075f,.12f,"79E9BF").gameObject;
                station.OffLamp=Models.Block(stand,"Offline lamp",new Vector3(0,1.03f,-.23f),
                    .28f,.075f,.12f,"EA9B73").gameObject;
            }
            stations.Add(station);
            map.RegisterTerminal(at);
            UpdateStationLamp(station);
        }

        private void UpdateStationLamp(Station station)
        {
            if(station.OnLamp==null) return;
            station.OnLamp.SetActive(economy.Powered);
            station.OffLamp.SetActive(!economy.Powered);
        }

        private Station NearbyStation()
        {
            float best=2.24f;
            Station next=null;
            foreach(Station station in stations)
            {
                Vector2 delta=station.Position-position;
                float gap=delta.magnitude;
                if(gap>=best) continue;
                // Check to the near face. The terminal itself is solid cover.
                Vector2 touch=position+delta.normalized*Mathf.Max(0,gap-.91f);
                if(map.FirstCover(position,touch)<1) continue;
                next=station;
                best=gap;
            }
            return next;
        }

        private string StationTitle(Station station) => station.Kind switch {
            StationKind.Weapon=>Weapons[station.Weapon].Name,
            StationKind.Ammo=>"Боекомплект +75",
            StationKind.Medkit=>"Аптечка +45",
            StationKind.Power=>"Подстанция",
            StationKind.Armor=>"Защитный комплект",
            StationKind.Mobility=>"Комплект подвижности",
            StationKind.Calibration=>"Доработка оружия",
            _=>"Случайное оружие"
        };

        private int StationPrice(Station station) => station.Kind switch {
            StationKind.Weapon=>WeaponPrices[station.Weapon],
            StationKind.Ammo=>260,
            StationKind.Medkit=>320,
            StationKind.Power=>RunEconomy.PowerPrice,
            StationKind.Armor=>1150,
            StationKind.Mobility=>1250,
            StationKind.Calibration=>economy.UpgradePrice(weaponId),
            _=>760
        };

        private string StationUnavailable(Station station)
        {
            if(station.RequiresPower && !economy.Powered) return "Нужно питание";
            switch(station.Kind)
            {
                case StationKind.Weapon: if(station.Weapon==weaponId) return "Уже в руках"; break;
                case StationKind.Power: if(economy.Powered) return "Питание подано"; break;
                case StationKind.Ammo: if(ammo>=MaxReserve) return "Запас полон"; break;
                case StationKind.Medkit: if(hp>=maxHp) return "Здоровье полное"; break;
                case StationKind.Armor: if(plated) return "Уже куплен"; break;
                case StationKind.Mobility: if(quickHands) return "Уже куплен"; break;
                case StationKind.Calibration:
                    if(economy.Tier(weaponId)>=RunEconomy.MaxTier) return "Оружие доработано до предела";
                    break;
            }
            return "";
        }

        private void Purchase(Station station)
        {
            string reason=StationUnavailable(station);
            if(reason.Length>0) { Announce(reason); return; }
            int cost=StationPrice(station);
            bool bought=station.Kind switch {
                StationKind.Power=>economy.TryPower(),
                StationKind.Calibration=>economy.TryUpgrade(weaponId),
                _=>economy.TrySpend(cost)
            };
            if(!bought) { Announce("Не хватает "+(cost-economy.Points)+" очков"); return; }
            string result=StationTitle(station);
            switch(station.Kind)
            {
                case StationKind.Weapon:
                    EquipPurchasedWeapon(station.Weapon);
                    break;
                case StationKind.Case:
                    int stock=Random.Range(0,Weapons.Length-1);
                    if(stock>=weaponId) stock++;
                    EquipPurchasedWeapon(stock);
                    result=Weapons[stock].Name;
                    break;
                case StationKind.Ammo:
                    int added=Mathf.Min(75,MaxReserve-ammo);
                    ammo+=added;
                    result="Боекомплект +"+added;
                    break;
                case StationKind.Medkit:
                    hp=Mathf.Min(maxHp,hp+45);
                    break;
                case StationKind.Power:
                    foreach(Station terminal in stations) UpdateStationLamp(terminal);
                    result="Питание подано";
                    break;
                case StationKind.Armor:
                    plated=true;
                    maxHp+=35;
                    hp+=35;
                    armor*=.85f;
                    break;
                case StationKind.Mobility:
                    quickHands=true;
                    speed*=1.12f;
                    dashCooldown*=.80f;
                    break;
                case StationKind.Calibration:
                    reloadTimer=0;
                    result=Weapons[weaponId].Name+" · МК "+economy.Tier(weaponId);
                    break;
            }
            Sound(station.Kind==StationKind.Power?"wave":"pickup");
            Announce(result+"  −"+cost+" очков");
        }

        private void DrawStationSigns(float scale)
        {
            foreach(Station station in stations)
            {
                Vector2 delta=station.Position-position;
                if(delta.sqrMagnitude>26) continue;
                Vector2 front=station.Position-delta.normalized*.92f;
                if(map.FirstCover(position,front)<1) continue;
                Vector2 point=Project(station.Position,1.38f,scale);
                string name=StationTitle(station);
                float width=Mathf.Clamp(small.CalcSize(new GUIContent(name)).x+18,95,255);
                var label=new Rect(point.x-width/2,point.y-10,width,23);
                Fill(label,new Color(.10f,.16f,.24f,.87f));
                GUI.Label(new Rect(label.x+7,label.y,label.width-14,label.height),name,small);
            }
        }

        private void EquipPurchasedWeapon(int index)
        {
            // Keep the ammo left in the old gun. Each new weapon includes a magazine.
            ammo=Mathf.Min(MaxReserve,ammo+magazine);
            weaponId=index;
            magazine=MagazineCapacity;
            reloadTimer=0;
            player.Equip(weaponId);
        }
    }
}
