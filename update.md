/using-superpowers:skill

** Aşağıdaki güncelleme isteklerini incele ve uygun "IMPLEMENTATION_PLAN" oluştur. Kod yapısına göre hatasız ekleme ve değiştirme planını detaylı şekilde hazırla, gözden geçir, kontrol et ve uygulamaya hazır olduğunda bildir. **

# vega-nesting Yapılacak Güncellemeler

## 1-Sac Genisligi ve Sac Yuksekligi Secimi Duzeltme
Sac Genisligi ve Sac Yuksekligi girmemize rağmen output olarak parcalari sigdirdigi dikdörtgeni veriyor, bunun yerine girdigimiz sacin ölcülerine cerceve oalrak kullanması gerekiyor.

## 2- Maks Sac Adedi 
Bu parametre inputlardan kaldirilmali, biz sac ölcülerini girdikten sonra yerlesim yapılır, girilen parca adetlerine göre de kaç adet sac gerektiğini söyler. Eğer her sacdaki dizilim aynı değilse outpu olarak, farklı dizilimleri ve her dizilimden kaç adet olacağını yazması gerekir. Kaç farklı dizilim varsa hepsini ayrı indirilebilir dxfler olarak çıkartmalı. 

Örnek output: 
    Dizilim-1 :
        Sac: 3000x3000
        Adet: 4
        <svg> 

    Dizilim-2 :
        Sac:3000x3000
        Adet: 2
        <svg-2>


### Eklenecek Inputlar
Çıktı adı input box yanına ek olarak sacın malzemesini input olarak eklemeliyiz. EnumList olarak (st37, aluminyum, st52, 304, vs.) açılır liste olmalı, farklı değerlere de izin vermeli (listede olmayan değer girilebilir). 

### Default Degerler
Parcalara DXF dosyası yüklenirken bu dosyaların isimlendirmesinde bir standart vardır. "Parca İsmi"-"malzeme"-"sac kalınlık"-"adet". Bu isimlendirmeden yola çıkarak yüklenilen DXF dosyalarından output DXF dosyasının isimlendirmesinde kullanılmak üzere sac malzemesini ve kalınlığını çekmeye çalışcağız, arayüzden çekilen değer düzenlenebilecek. 

Örnek: "DT000676_3_1-st37-3mm-1adet.dxf" dosyası için:
        parca_ismi = DT000676_3_1
        sac_malzeme = st37  
        sac_kalinlik = 3mm
        adet = 1   # adet bazı dosyalarda olmayabilir, "açıkça" adet veya "ad." yazıyorsa değeri çek yoksa çekme


### DXF Output 
Dizilimi indirilebilir DXF dosyasına çevirirken, dosyanın ismine default değer atamalıyız. Aşağıdaki syntax düzenlenmemiş if döngüsü isimlendirme mantığını anlaman içindir. Eğer dizilimde bir adet parça varsa
DXF dosyasının ismi "parca_ismi-malzeme-adet" şeklinde düzenlenmelidir. Eğer farklı parçalar varsa dosyanın default isimlendirmesi PROJE_ADI olmalıdır, proje adı girilmemişse "sac_genislik-sac_yukseklik-sac_kalinlik-malzeme" olmalıdır. Aşağıdaki formüldeki degisken isimlerine veya formülün syntax'ını görmzeden gel, mantığı anlaman içindir.

DXF dosyasının ismi parcanin adi
default_file_name= if count(unique(parcalar)) = 1
                        = "$parca_ismi"-"parca_adeti"
                    else
                        = "$SAC_GENISLIGI""x""SAC_YUKSEKLIGI"-"$SAC_ADEDI"-"$Sac_Malzeme"
    