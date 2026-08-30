using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;

namespace TrafficVisualizer
{
    public class Database
    {
        public string Airport { get; set; }
        public string Name { get; set; }
        public string DatabasePath { get; set; }
        public List<ScheduleLine> Schedule { get; set; } = new();
        public int GADepartures { get; set; }
        public int GAArrivals { get; set; }
        public int Departures { get; set; }
        public int Arrivals { get; set; }
        public int CargoArrivals { get; set; }
        public int CargoDepartures { get; set; }
        public List<GALine> GA { get; set; } = new();

        public ushort[] Distribution = new ushort[144];
        public Dictionary<string,ushort> Operators = new();
        public Dictionary<string, ushort> Types = new();
        public List<ItemCount> TopOperators { get; set; } = new();
        public List<ItemCount> TopAircraft { get; set; } = new();
        public bool IsLoaded { get; set; } // database is only loaded when selected

        public Database(string airport, string path) {
            Airport = airport;
            DatabasePath = path;
            Name = Path.GetFileName(path);
            IsLoaded = false;
        }

        private bool sepCargo = false;
        public void Load(bool separateCargo=false) { 
            if (IsLoaded && separateCargo==sepCargo) return;
            string line;
            int lineno = 2;
            // enumerate schedule
            Distribution = new ushort[144];
            Arrivals = 0;
            CargoArrivals = 0;
            CargoDepartures = 0;
            Departures = 0;
            GAArrivals = 0;
            GADepartures = 0;
            if (File.Exists(DatabasePath + "\\schedule.csv")) {
                Schedule = new();
                using (TextReader reader = new StreamReader(DatabasePath + "\\schedule.csv")) { 
                    try {
                        reader.ReadLine();
                        while ((line=reader.ReadLine())!=null) {
                            var sch=ScheduleLine.Parse(line);
                            if (sch != null) Schedule.Add(sch);
                        }
                        foreach (var schedule in Schedule) {
                            if (!string.IsNullOrEmpty(schedule.ApproachTime)) {
                                if (separateCargo && schedule.IsCargo) {
                                    Distribution[int.Parse(schedule.ApproachTime.Substring(0, 2)) * 6 + 4]++;
                                    CargoArrivals++;
                                } else {
                                    Distribution[int.Parse(schedule.ApproachTime.Substring(0, 2)) * 6]++;
                                    Arrivals++;
                                }
                            }
                            if (!string.IsNullOrEmpty(schedule.DepartureTime)) {
                                if (separateCargo && schedule.IsCargo) {
                                    Distribution[int.Parse(schedule.DepartureTime.Substring(0, 2)) * 6 + 5]++;
                                    CargoDepartures++;
                                } else {
                                    Distribution[int.Parse(schedule.DepartureTime.Substring(0, 2)) * 6 + 1]++;
                                    Departures++;
                                }
                            }
                            if (!string.IsNullOrEmpty(schedule.OperatorColor))
                                if (Operators.ContainsKey(schedule.OperatorColor))
                                    Operators[schedule.OperatorColor]++;
                                else Operators[schedule.OperatorColor] = 1;
                            if (!string.IsNullOrEmpty(schedule.AirplaneType)) 
                                if (Types.ContainsKey(schedule.AirplaneType))
                                    Types[schedule.AirplaneType]++;
                                else Types[schedule.AirplaneType] = 1;
                            lineno++;
                        }
                    } catch (Exception ex) {
                        MessageBox.Show($"Error loading schedule on line {lineno}: {ex.Message}");
                        return;
                    }
                }
            }
            // enumerate GA schedule
            if (File.Exists(DatabasePath + "\\ga.csv")) {
                GA = new();
                using (TextReader reader = new StreamReader(DatabasePath + "\\ga.csv")) { 
                    try {
                        reader.ReadLine();
                        while ((line = reader.ReadLine()) != null) {
                            var ga = GALine.Parse(line);
                            if (ga != null) GA.Add(ga);
                        }
                        lineno = 2;
                        foreach (var ga in GA) {
                            if (!string.IsNullOrEmpty(ga.ArriveTime)) {
                                Distribution[int.Parse(ga.ArriveTime.Substring(0, 2)) * 6 + 2]++;
                                GAArrivals++;
                            }
                            if (!string.IsNullOrEmpty(ga.DepartureTime)) {
                                Distribution[int.Parse(ga.DepartureTime.Substring(0, 2)) * 6 + 3]++;
                                GADepartures++;
                            }
                            if (!string.IsNullOrEmpty(ga.AirplaneType))
                                if (Types.ContainsKey(ga.AirplaneType))
                                    Types[ga.AirplaneType]++;
                                else Types[ga.AirplaneType] = 1;
                            lineno++;
                        }
                    } catch (Exception ex){
                        MessageBox.Show($"Error loading ga schedule line {lineno}: {ex.Message}");
                        return;
                    }
                }
            }
            // top operators and aircraft
            TopOperators = Operators.Keys.Select(o => new ItemCount { Item = o, Count = Operators[o] }).OrderBy(o => -o.Count).Take(10).ToList();
            TopAircraft = Types.Keys.Select(o =>new ItemCount { Item = o, Count = Types[o] }).OrderBy(o => -o.Count).Take(10).ToList();
            IsLoaded = true;
            sepCargo = separateCargo;
        }
    }

    public class ItemCount
    {
        public string? Item { get; set; }
        public int Count { get; set; }
    }
}
