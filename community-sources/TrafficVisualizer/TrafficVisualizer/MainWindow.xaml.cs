using System.IO;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;

namespace TrafficVisualizer
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {

        public MainWindow()
        {
            InitializeComponent();
            LoadAirports();
        }

        List<Airport> Airports = new();
        string? InstallPath = null;
        private void LoadAirports()
        {
            // get installation folder
            string LogPath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData)+ @"\..\LocalLow\FeelThere Inc_\Tower! Simulator 3\Player.log";
            if (File.Exists(LogPath)) {
                using (TextReader reader = new StreamReader(LogPath)) {
                    string? firstLine = reader.ReadLine();
                    try {
                        InstallPath = firstLine?.Substring(16, firstLine.Length - 48).Replace("/", "\\");
                    } catch (Exception) {
                        MessageBox.Show("Error finding Tower! Simulator 3");
                        return;
                    }
                }
            }
            // get airports
            foreach (var airportDir in Directory.GetDirectories(InstallPath + "Airports")) {
                string? icao = System.IO.Path.GetFileName(airportDir);
                Airport airport=new Airport { ICAO=icao};
                foreach (var database in Directory.GetDirectories(airportDir + "\\databases")){
                    airport.Databases.Add(new Database(icao,database ));
                }
                Airports.Add(airport);
            }
            lbAirports.ItemsSource = Airports;
        }

        private void lbAirports_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            lvDatabases.SelectedIndex = 0;
        }

        private void lvDatabases_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            Database? database = lvDatabases.SelectedItem as Database;
            database?.Load(sepCargo.IsChecked==true);
            if (database?.IsLoaded == true) {
                Chart.SeparateCargo = sepCargo.IsChecked == true; 
                Chart.C.DataContext = database;
                Chart.lbAircraft.ItemsSource = database.TopAircraft;
                Chart.lbOperators.ItemsSource = database.TopOperators;
            }
        }

        private void CreateBitmapFromCanvas(string filename)
        {
            if (Chart.C == null) return;
            try {
                Canvas C = Chart.C;

                Size size = new Size( C.ActualWidth, C.ActualHeight);
                C.Arrange(new Rect(size));

                RenderTargetBitmap bmp = new RenderTargetBitmap((int)size.Width, (int)size.Height, 96d, 96d, PixelFormats.Pbgra32);
                bmp.Render(C);

                PngBitmapEncoder encoder = new PngBitmapEncoder();
                encoder.Frames.Add(BitmapFrame.Create(bmp));

                System.IO.FileStream stream = System.IO.File.Create(filename);
                encoder.Save(stream);
                stream.Close();
            } catch (Exception ex) {
                MessageBox.Show($"Error saving screen: {ex.Message}");
            }
        }

        private void Button_Click(object sender, RoutedEventArgs e)
        {
            Database? db=lvDatabases.SelectedItem as Database;
            if (db?.IsLoaded==true) {
                string filename = $"{db.Airport}-{db.Name}.png";
                CreateBitmapFromCanvas (filename);
            }
        }
    }
}