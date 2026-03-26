import re

# Paste the provided text into this multiline string variable
text_content = """
                                                                                           90 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name      Yangrong CAO             Gender                   Man 

         Position Title                           Professor 

     Working Department 

    Email                         yrcao@mail.hzau.edu.cn 

  Address 

     Tel                  027-87281687                    Fax 

Research Interest 

     The molecular basis of legume-rhizobial symbiosis. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      2004-2008: Ph.D., Institute of Genetics and Developmental Biology, Chinese Academy of 

 Sciences, Beij ing, China 

      2001-2004: Master, Key Lab of Plant Stress Research, Shandong Normal University, 

 Jinan, China 

      1997-2001: Bachelor, Department of Biology, Shandong Normal University, Jinan, China 

 Professional Experiences: 
﻿     2015-present: Professor, National Key Lab of Agricultural University and College of Life 

Science and Technology, Huazhong agricultural University. 

     2012-2015: Postdoctoral Research Associate, Division of Plant Sciences and National 

Center for Soybean Biotechnology, University of Missouri. 

     Supervisor: Prof. Gary Stacey 

     2008-2012: Postdoctoral Research Associate, Department of Plant pathology, University of 

Wisconsin-Madison. 

     Supervisor: Prof. Andrew F. Ben 

Publications 

    1. Huang R, Li Z, Mao C, Zhang H, Sun Z, Li H, Huang C, Feng Y, Shen X, Bucher M, 

       Zhang Z, Lin Y, Cao Y*, Duanmu D*. 2019. Natural variation at OsCERK 1 regulates 

        arbuscular mycorrhizal symbiosis in rice. New Phytol. DOI: 10.1111/nph.16158 

    2. Yin J, Guan X, Zhang H, Wang L, Li H, Zhang Q, Chen T, Xu Z, Hong Z, Cao 

       Y*, Zhang Z*. 2019. An MAP kinase interacts with LHK 1 and regulates nodule 

        organogenesis in Lotus j aponicus. Sci China Life Sci. 62(9):1203-12 17 

    3. Yu H, Bao H, Zhang Z, Cao Y*. 2019. Immune signaling pathway during terminal 

       bacteroid differentiation in nodules.Trends Plant Sci. 24: 299-3024. 

    4. Zhang L, Liu JY, Gu H, Du Y, Zuo JF, Zhang Z, Zhang M, Li P, Dunwell JM, Cao Y, 

       Zhang Z, Zhang YM. 2018. Bradyrhizobium diazoefficiens USDA 110- Glycine max 

       Interactome Provides Candidate Proteins Associated with Symbiosis. J Proteome 

       Res. 17:3061-3074 

    5. Yu H, Xiao A, Dong R, Fan Y, Zhang X, Liu C, Wang C, Zhu H, Duanmu D, Cao Y*, 

       Zhang Z*. 2018. Suppression of innate immunity mediated by the CDPK ‐Rboh 

        complex is required for rhizobial colonization in Medicago truncatula nodules. New 

       Phytol. 220: 425-434 

    6. Li H, Chen M, Duan L, Zhang T, Cao Y, Zhang Z. 2018. Domain swap approach reveals 
﻿    the critical roles of different domains of SymRK in root nodule symbiosis in Lotus 

    j aponicus. Front Plant Sci. 9:697 

7. Chen D, Cao Y, Li H, Kim D, Ahsan N, Thelen J, Stacey G. 20 17. Extracellular ATP elicits 

    DORN 1-mediated RBOHD phosphorylation to regulate stomatal aperture. Nat Commun. 20 17 8: 

    2265. 

8.  Chen T, Duan L, Zhou B, Yu H, Zhu H, Cao Y, Zhang Z. 2017. Interplay of 

    Pathogen-Induced Defense Responses and Symbiotic Establishment in Medicago 

    truncatula. Front. Microbiol. 8:973 

9. Liao    D#,   Cao    Y#,   Sun    X,  Espinoza     C,  Nguyen     CT,   Liang    Y,   Stacey   G. 

    2017.  Arabidopsis  E3  ubiquitin     ligase  PLANT  U-BOX 13       (PUB 13)  regulates  chitin 

    receptor  LYSIN     MOTIF     RECEPTOR       KINASE5      (LYK5)     protein  abundance.  New 

    Phytol. 2 14:1646-1656. 

10.  Cao Y, Halane MK, Gassmann W, Stacey G. 2017. The role of plant innate immunity in 

    the legume-rhizobium symbiosis. Annu. Rev. Plant Biol. 68:535-561 

11.  Nguyen CT, Tanaka K, Cao Y, Cho SH, Xu D, Stacey G. 2016. Computational Analysis 

    of the Ligand Binding Site of the Extracellular ATP Receptor, DORN 1. PLoS One. 11: 

    e0161894. 

12.  Wang C, Yu H, Luo L, Duan L, Cai L, He X, Wen J, Mysore KS, Li G, Xiao A, 

    Duanmu D, Cao Y, Hong Z, Zhang Z.2016. NODULES WITH ACTIVATED 

    DEFENSE 1 is required for maintenance of rhizobial endosymbiosis in Medicago 

    truncatula. New Phytol. 2 12:176-91. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name       Wenli CHEN             Gender                 Woman 

         Position Title                          Professor 

     Working Department 

    Email                       wlchen@mail.hzau.edu.cn 

  Address 

     Tel                  027-87282730                   Fax 

Research Interest 

     Soil and Environmental Microbiology 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

 Ph.D. 1994 Huazhong Agricultural University, China 

 B.Sc. 1989 Huazhong Agricultural University, China 

 Professional Experiences: 

 2005.12-Present   Professor of Microbiology,chnology,      Huazhong Agricultural 

 University, China 

 2002.03-2004.03    Visiting Scientist , National  Institute of Agrobiological Sciences, Japan 

 1999.03-2000.09  Visiting Scientist, Yamaguchi      University, Japan 
﻿1997.05-1997.08  Visiting Scientist, Wagenigen       Agricultural University, the Netherlands 

1996.12-2005.12     Associate Professor, Huazhong      Agricultural University, China 

1994.06-1996.12     Lecturer, Huazhong Agricultural      University, China 

Publications 

1.   Cong  Zhou,  Juyuan  Zhang,  Xinyu  Hu,  Changchang  Li,  Li  Wang,  Qiaoyun  Huang  and 

     Wenli  Chen*.  2020  RNase  II  binds  to  RNase  E  and  modulates  its  endoribonucleolytic 

     activity  in  the   cyanobacterium    Anabaena     PCC    7120.   Nucleic   Acids    Research, 

      （https://doi.org / 10.1093/nar/gkaa092 ） 

2.   Li Wang, Xiang Xiong, Xuesong Luo, Wenli Chen, Shilin Wen, Boren Wang, Chengrong 

     Chen,  Qiaoyun  Huang*  2020 Aggregational  differentiation  of  ureolytic  microbes  in  an 

     Ultisol  under  long-term   organic   and  chemical    fertilizations. Science  of  The   Total 

     Environment, 716: 137103. 

3.   Xuesong Luo, Hang Qian, Li Wang, Shun Han, Shilin Wen, Boren Wang, Qiaoyun Huang*, 

     Wenli  Chen* 2019  Fertilizer  types  shaped  the microbial  guilds  driving  the  dissimilatory 

     nitrate reduction to ammonia process in a Ferralic Cambisol. Soil Biology & Biochemistry, 

     14 1: 107677 

4.   Yuj ie Xiao, Huizhong Liu, Meina He, Liang Nie, Hailing Nie, Wenli Chen* and Qiaoyun 

     Huang*  2019  A  crosstalk  between    c-di-GMP  and  cAMP  in  regulating  transcription    of 

     GcsA,   a diguanylate   cyclase  involved  in  swimming    motility  in Pseudomonas  putida. 

     Environmental Microbiology, 22(1):142-157. 

5.   Chenchen    Qu,  Wenli  Chen*,  Xiping   Hu,   Peng  Cai,  Chengrong    Chen,  Xiao-Ying  Yu, 

     Qiaoyun Huang* 2019 Heavy metal behaviour at mineral-organo interfaces: Mechanisms, 

     modelling and influence factors. Environmental International, 131: 104995. 

6.   Chenchen   Qu,  Shufang  Qian,  Liang    Chen,  Yong  Guan,  Lei  Zheng,  Shuhu    Liu,  Wenli 

     Chen*, Peng Cai, and Qiaoyun Huang* 2019 Size-dependent bacterial toxicity of hematite 

     particles. Environmental Science & Technology, 53(14): 8147-8156. 

7.   Shaozu Xu, Yonghui Xing, Song Liu, Qiaoyun Huang* & Wenli Chen* 2019 Role of novel 

     bacterial Raoultella sp. strain X 13 in plant growth promotion and cadmium bioremediation 

     in soil. Appl Microbiol Biotechnol. DOI 10.1007/s00253-019-09700-7 

8.   Shaozu Xu, Xuesong Luo, Yonghui Xing,  Song Liu, Qiaoyun Huang, Wenli Chen* 2019 

     Complete genome  sequence of Raoultella sp. strain X 13, a promising cell factory  for the 
﻿     synthesis        of       CdS         quantum         dots.       3        Biotech.        9:120 

     https://doi.org/ 10.1007/s13205-019-1649-0 

9.   Shun Han, Xiang Xiong, Xuesong Luoa, Luyang Zeng, Dan Wei, Wenli Chen ∗, Qiaoyun 

     Huang* 2018 Fertilization rather  than  aggregate  size fractions shape the nitrite-oxidizing 

     microbial   community     in  a  Mollisol.   Soil  Biology    &   Biochemistry,    124:179-183. 

     (DOI:10.1016/j .soilbio.2018.06.015). 

10.  Shun  Han,  Luyang  Zeng, Xuesong  Luo,  Xiang  Xiong,  Shilin  Wen, Boren  Wang, Wenli 

     Chen*, Qiaoyun  Huang* 2018  Shifts in Nitrobacter- and Nitrospira-like nitrite-oxidizing 

     bacterial communities under long-term fertilization practices. Soil Biology & Biochemistry, 

     124:118-125 

11.  Li  Wang, Xuesong  Luo, Hao  Liao, Wenli  Chen*, Dan  Wei, Peng  Cai,  Qiaoyun  Huang* 

     2018 Ureolytic microbial community is modulated by fertilization regimes and particle-size 

     fractions  in  a  Black   soil  of  Northeastern   China.   Soil  Biology    and   Biochemistry 

     116:171-178 

12.  Yuj ie  Xiao,  Wenj ing  Zhu,  Huizhong  Liu,  Hailing  Nie,  Wenli  Chen*,  Qiaoyun  Huang* 

     2018 FinR  Regulates Expression  of nicC  and nicX  Operons, Involved  in Nicotinic Acid 

     Degradation in Pseudomonas putida KT2440. Appl Environ Microbiol. 84(20):e012 10-18 

13.  Shun Han, Xiang Li, Xuesong Luo, Shilin Wen, Wenli Chen* and Qiaoyun Huang* 2018 

     Nitrite-Oxidizing   Bacteria  Community     Composition    and   Diversity  Are  Influenced   by 

     Fertilizer Regimes, but Are Independent  of the  Soil Aggregate in Acidic  Subtropical Red 

     Soil. Front. Microbiol.,https://doi.org/ 10.3389/fmicb.2018.00885 

14.  Hao  Liao,  Yuchen    Zhang,  Qinyan   Zuo,  Binbin   Du,  Wenli   Chen*,  Dan    Wei,  Qiaoyun 

     Huang*. 2018 Contrasting responses of bacterial and fungal communities to aggregate-size 

     fractions  and  long-term  fertilizations  in soils  of  northeastern China.  Sci  Total  Environ 

     635:784-792. 

15.  Shun  Han, Xuesong  Luo, Hao  Liao, Hailing Nie, Wenli  Chen*,  Qiaoyun  Huang*. 2017 

     Nitrospira are more sensitive than Nitrobacter to land management in acid, fertilized soils 

     of a rapeseed-rice rotation field trial. Sci Total Environ 599-600:135-144. 

16.  Qi Li, Huihui Du, Wenli Chen*, Jialong Hao, Qiaoyun Huang*, Peng Cai, Xionghan Feng 

     2017   Aging   Shapes   the  Distribution   of  Copper    in Soil  Aggregate    Size  Fractions. 

     Environmental Pollution. 233: 569-576 (DOI:10.1016/j .envpol.2017.10.091). 
﻿17.  Xuesong Luo, Xiaoqian Fu, Yun Yang, Peng Cai, Shaobing Peng, Wenli Chen* & Qiaoyun 

     Huang 2016 Microbial communities play important roles in modulating paddy soil fertility. 

     Sci. Rep. 6, 20326; doi: 10.1038/srep20326. 

18.  Caijuan  Peng,  Songsong  Lai,  Xuesong  Luo,  Jianwei  Lu,  Qiaoyun  Huang,  Wenli  Chen* 

     2016 Effects of Long term rice straw application on the microbial communities of rapeseed 

     rhizosphere  in a  paddy-upland   rotation  system.  Science  of  the  Total Environment, 

     557-558:231-239. (DOI:10.1016/j .scitotenv.2016.02.184). 

19.  Du,  Huihui;  Wenli  Chen*,  Peng   Cai, Xingmin   Rong,   Ke  Dai,  Caroline L.  Peacock, 

     Qiaoyun   Huang*    2016    Cd(II)  Sorption   on  Montmorillonite-Humic      acid-Bacteria 

     Composites. Scientific Reports, 6:19499. (DOI: 10.1038/srep 19499) 

20. Ning Wang, Huihui Du, Qiaoyun Huang*, Peng Cai, Xingmin Rong, Xionghan Feng and 

     Wenli Chen* 2016 Surface complexation modeling of Cd(II) sorption to montmorillonite, 

     bacteria, and their composite. Biogeosciences, 13:5557–5566. (doi:10.5194/bg-13-1-2016) 

2 1. Huihui Du, Wenli Chen, Pen Cai, Xingmin Rong, Chenrong Chen & Qiaoyun Huang 2016 

     Cadmium  adsorption  on bacteria–mineral mixtures: Effect  of naturally  occurring ligands. 

     European Journal of Soil Science, 67: 64 1–649 (doi: 10.1111/ej ss.12373). 

22.  Lu  Xia, Xingj ian  Xu, Wei  Zhu,  Qiaoyun  Huang*  and Wenli  Chen  2015 A  Comparative 

     Study on the Biosorption of Cd2+ onto Paecilomyces lilacinus XLA and Mucoromycote sp. 

     XLC.     International    Journal    of    Molecular     Sciences,     16:    15670-15687 

     (doi:10.3390/ij ms160715670). 

23.  Zhineng Hong, Wenli  Chen*, Xingmin  Rong, Peng  Cai, Wenfeng Tan, Qiaoyun  Huang* 

     2015 Effects of humic acid on adhesion of Bacillus subtilis to phyllosilicates and goethite. 

     Chemical Geology 4 16:19-27. 

24.  Huayong   Wu,Wenli    Chen,   Xingmin    Rong,Peng   Cai,Ke   Dai,Qiaoyun    Huang.   2014 

     Adhesion  of  Pseudomonas  putida  onto  kaolinite  at different growth  phases.  Chemical 

     Geology. 390:1-8 

25.  Ming Li, Xue Tian, Rong-Zi Liu, Wen-Li  Chen, Peng Cai, Xing-Min Rong, Ke Dai, and 

     Qiao-Yun  Huang.  2014   Combined  Application    of  Rice Straw  and  Fungus  Penicillium 

     Chrysogenum     to  Remediate    Heavy-Metal-Contaminated      Soil.  Soil  and   Sediment 

     Contamination: An International Journal. 23(3): 328-338 

26.  Huayong Wu, Wenli  Chen, Xingmin  Rong, Peng  Cai, Ke Dai  &  Qiaoyun  Huang*. 2014 
﻿     Soil  colloids and minerals modulate metabolic  activity  of Pseudomonas putida measured 

     using microcalorimetry. Geomicrobiology Journal, 31: 590–596 

27.  Zhineng  Hong,  Gang  Zhao,  Wenli  Chen,  Xingmin         Rong,  Peng  Cai,  Ke  Dai,  Qiaoyun 

     Huang. 2014 Effects of Solution Chemistry on Bacterial Adhesion with Phyllosilicates and 

     Goethite Explained by the Extended DLVO Theory. Geomicrobiology Journal 31: 4 19-430. 

28.  Huayong Wu, Wenli Chen, Xingmin Rong, Peng Cai, Ke Dai, Qiaoyun Huang. 2014                      In 

     situ ATR-FTIR  study on the adhesion of Pseudomonas putida to Red soil colloids. J Soils 

     Sediments 14: 504-514. 

29.  Zhineng Hong, Wenli Chen, Xingmin Rong, Peng Cai, Ke Dai, Qiaoyun Huang. 2013 The 

     effect  of  extracellular  polymeric  substances  on  the  adhesion  of bacteria to  clay  minerals 

     and goethite. Chemical Geology 360–361:118– 125. 

30.  Xu  Xingj ian,  Xia  Lu,  Huang    Qiaoyun,  Gu    Ji-Dong,  Chen  Wenli  2012  Biosorption      of 

     cadmium by  a metal-resistant  filamentous fungus isolated from  chicken manure compost. 

     Environmental Technology, 33: 1661-1670. 
﻿                            CURRICULUM VITAE 

Personal Information 

                  Deqiang 
    Name                               Gender                  Man 
                 DUANMU 

         Position Title                          Professor 

     Working Department 

    Email                       duanmu@mail.hzau.edu.cn 

  Address 

     Tel                   186940672 18                  Fax 

Research Interest 

     Photosynthetic  mechanism  and  synthetic  biology;  Symbiotic  nitrogen  fixation  and  nodule 
     development; Chloroplast retrograde signaling; Tetrapyrrole metabolism; 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      1995-1999, B.S., Biophysics, Peking University. 

      1999-2002, M.S., Cell biology, Chinese Academy of Sciences. 

      2002-2009, Ph.D., Plant Biology, Iowa State University,. 

 Professional Experiences: 

      2009-2014, Postdoctoral researcher, UC Davis. 

      2014-present, Professor, College of Life Science and Technology, Huazhong Agricultural 
﻿University (HZAU). 

Publications 

1.    Huang R, Li Z, Mao C, Zhang H, Sun Z, Li H, Huang C, Feng Y, Shen X, Zhang Z, Lin Y, 

              #                # 
     Cao  Y ,  Duanmu        D .  Natural    variations    at  OsCERK 1  regulate        arbuscular    mycorrhizal 

     symbiosis in rice. New Phytol, 2019 Sep 4. doi: 10.1111/nph.16158. 

2.      Wang L, Maria C, Xin X, Zhang B, Fan  Q, Wang Q, Ning G, Becana M, Duanmu  D. 

     CRISPR/Cas9         knockout     of   leghemoglobin       genes    in   Lotus   j aponicus    uncovers     their 

     synergistic roles in symbiotic nitrogen fixation. New Phytol, 2019, 224(2):818-832. 

3.    Wittkopp TM, Schmollinger S, Saroussi S, Hu W, Zhang W, Fan Q, Gallaher SD, Leonard 

                                                                                                   #                # 
     MT,  Soubeyrand  E,  Basset  GJ, Merchant  SS,  Grossman  AR, Duanmu  D ,  Lagarias  JC . 

     Bilin-dependent       photoacclimation        in   Chlamydomonas         reinhardtii.    Plant    Cell,   2017, 

     29(11):2711-2726. 

                    #                                   # 
4.     Duanmu D , Rockwell NC, Lagarias JC . Algal Photomorphogenesis and Light Sensing in 

     Aquatic Environments. Plant Cell Environ, 2017, 40(11):2558-2570. 

                                                                                        #               # 
5.        Wang  L, Wang  L,  Tan  Q, Fan  Q, Zhu  H, Hong  Z, Zhang  Z , Duanmu  D . Efficient 

     Inactivation     of  Symbiotic  Nitrogen       Fixation    Related    Genes     in  Lotus  j aponicus  Using 

     CRISPR-Cas9. Front. Plant Sci, 2016, 7:1333 

6.     Duanmu D*, Bachy C*, Sudek S, Wong CH, Jimenez V, Rockwell NC, Martin SS, Ngan 

     CY,  Reistetter     EN,  van     Baren   MJ,  Price  DC,  Wei        CL,  Reyes-Prieto  A,  Lagarias  JC, 

     Worden      AZ.    Marine     algae   and   land    plants   share   conserved      phytochrome       signaling 

     systems. Proc Natl Acad Sci USA, 2014, 111(44):15827-15832. 

7.    Duanmu D, Casero D, Dent RM, Gallaher S, Yang W, Rockwell NC, Martin SS, Pellegrini 

     M,  Niyogi     KK,  Merchant        SS,  Grossman      AR,  Lagarias  JC.  Retrograde  bilin          signaling 

     enables  Chlamydomonas  greening  and  phototrophic  survival.  Proc  Natl  Acad  Sci  USA, 

     2013, 110(9):362 1-3626. 
﻿8.       Duanmu  D,  Spalding MH. Insertional  suppressors  of  Chlamydomonas reinhardtii that 

     restore    growth    of   air-dier   lcib   mutants     in   low    CO .2  Photosynth      Res,    2011,109 

     (1-3):123-132. 

9.          Duanmu      D,  Miller   AR,  Horken      KM,  Weeks  DP,        Spalding  MH.  Knockdown           of 

     limiting-CO -induced gene HLA3 decreases HCO -                transport and photosynthetic Ci-affinity 
                    2                                            3 

     in Chlamydomonas reinhardtii. Proc Natl Acad Sci USA, 2009, 106(14):5990-5995. 

10.      Duanmu     D,  Wang  Y,      Spalding  MH.  Thylakoid         lumen    carbonic    anhydrase    (CAH3) 

     mutation      suppresses      air-Dier    phenotype       of   LCIB      mutant     in    Chlamydomonas 

     reinhardtii. Plant Physiol, 2009, 149(2):929-937. 
﻿                              CURRICULUM VITAE 

Personal Information 

    Name       Mingqian FENG              Gender 

          Position Title                             Professor 

     Working Department 

    Email                      Fengmingqian@mail.hzau.edu.cn 

   Address 

      Tel                    02787282669                      Fax 

Research Interest 

     Our  lab  is focusing  on translational medicine  studies, with the ultimate goal  of  developing 

cancer  immunotherapy  drugs and technologies. Currently, we  are  focusing  on  antibody-derived 

therapeutics   and  adoptive   transfer of  engineered   of  immune    cells.  For  the antibody-derived 

therapeutics,  we  are  working  at  bi-specific  antibody   and   antibody-drug  conjugate  (ADC).  In 

particular,  we’re  interested  in  understanding  the  role  of  cancer  specific  membrane  proteins  in 

tumor biology and generating novel antibody-based therapeutic agent targeting tumor biomarkers. 

One of the examples that we’re working with is liver cancer biomarker GPC3 and the hippo-yap 

pathway. For the engineering of immune cells, we are working at the new generation of chimeric 

antigen receptor-modified immune cells. 

     We  also  have  broad  interest   in antibody   engineering  filed,  including  but  not  limited  to, 

antibody   display   technologies   (phage   display,   yeast  display,  mammalian      display),  domain 

antibodies  (camelid,  shark,  human,  and  other  protein  scaffold-derived  binders),  antibody-drug 

conjugation, and modification of antibody characteristics (enhanced ADCC and CDC, prolonged 

half-life, improved stability, etc.). 

Professional Memberships 
﻿Other Roles 

 Education & Working Experience 

 Education : 

      1993.09-1997.07  B.A. Northwestern  Agricultural  University,  maj ored  in  Crop  Genetics 

 and Breeding, Yangling, Shaanxi 712 100, China 

      1997.09-2000.07    M.S.   Northwest   Agriculture   &  Forestry   University,  maj ored  in 

 Biochemistry and Molecular Biology, Yangling, Shaanxi 712 100, China 

      2005.09-2008.06, Ph.D. Nanj ing University, maj ored in Biology, Nanj ing, Jiangsu 2 10093, 

 China 

 Professional Experiences: 

      2000.07-2005.09,  Instructor  on Biochemistry   and  Molecular  Biology,  College  of  Life 

 Science and Technology, Huazhong Agricultural University, Wuhan, Hubei 430070, China 

      2008.10-2013.10, Post-doctoral training in antibody engineering, Laboratory of Molecular 

 Biology (LMB), National Cancer Institute (NCI), National Institutes of Health (NIH), Bethesda, 

 MD. 

      2013.10-2015.11, Research Fellow, National Cancer Institute, NIH, Bethesda, MD 

 Publications 

 1.   Xin Chen, Norhan Amar, Yuankui Zhu, Chunguang Wang, Chunj iao Xia, Xiaoqing Yang, 

      Dongde  Wu,  Mingqian  Feng*. Combined  DLL3-targeted  bispecific  antibody  with  PD-1 

      inhibition is efficient to suppress small cell lung cancer growth. Journal for Immunotherapy 

      of Cancer. 2020 ；DOI: 10.1136/j itc-2020-000785 (in production) 

 2.   Dan  Li, Nan  Li  , Yi-Fan  Zhang, Haiying  Fu, Mingqian  Feng, Dina  Schneider, Ling  Su, 

      Xiaolin  Wu, Jing Zhou,  Sean  Mackay, Josh  Kramer, Zhij ian  Duan, Hongj ia Yang, Aarti 
﻿     Kolluri, Alissa M Hummer, Madeline B Torres, Hu Zhu, Matthew D Hall, Xiaoling Luo, 

     Jinqiu Chen, Qun Wang, Daniel Abate-Daga, Boro Dropublic, Stephen M Hewitt, Rimas J 

      Orentas, Tim F Greten, Mitchell Ho. Persistent polyfunctional chimeric antigen receptor T 

      cells  that  target   glypican    3  eliminate    orthotopic    hepatocellular     carcinomas     in  mice. 

      Gastroenterology 2020; 158(8):2250-2265. 

3.   Zhe Duan, Jingqiu Liu, Liping Niu, Jun Wang, Mingqian Feng*, Hua Chen*, Cheng Luo*. 

     Discovery  of  DC_H31 as  potential  mutant  IDH 1 inhibitor  through  NADPH-based  high 

     throughput screening. Bioorganic Medicinal Chemistry 2019; 27(15):3229-3236. 

                        #                 # 
4.   Mingqian  Feng ,  Hej iao  Bian ,  Xiaolin  Wu,  Tianyun  Fu,  Jessica  Hong,  Bryan  Fleming, 

     Martin  Flaj nik,  Mitchell  Ho.  Construction  and  next-generation  sequencing  analysis  of  a 

      large phage-displayed VNAR single domain antibody library from six naïve nurse sharks. 

     Antibody therapeutics, 2019, 2:1-11 

5.   Wei Gao, Heungnam Kim, Mingqian Feng, Yen Phung, Charles P Xavier, Jeffrey S Rubin, 

     Mitchell Ho. Immunotoxin targeting glypican-3 regresses liver cancer via dual inhibition of 

     Wnt signaling and protein synthesis. Nature Communications 2015; 6:6536. 

6.   Mingqian  Feng, Wei  Gao, Ruoqi Wang, Weizao  Chen, Yan-Gao Man, William  Douglas 

     Figg,    Xin   Wei    Wang,     Dimiter    S   Dimitrov,    Mitchell    Ho.    Therapeutically     targeting 

      glypican-3     via   a   conformation-specific        single-domain       antibody     in   hepatocellular 

      carcinoma. PNAS 2013; 110(12):E 1083-91. 

7.   Mingqian Feng, Jingli Zhang, Miriam Anver, Raffit Hassan, Mitchell Ho. In vivo imaging 

      of human  malignant  mesothelioma grown  orthotopically  in  the peritoneal  cavity  of nude 

     mice. Journal of Cancer 2011; 2:123-31. 

                  #                     # 
8.   Liping  Yu ,  Mingqian  Feng ,  Heungnam  Kim,  Yen  Phung,  David  E  Kleiner,  Gregory  J 

      Gores, Min Qian, Xin Wei Wang, Mitchell Ho. Mesothelin as a potential therapeutic target 

      in human cholangiocarcinoma. Journal of Cancer 2010; 1:14 1-9. 
﻿                             CURRICULUM VITAE 

Personal Information 

    Name       Wenyuan HAN             Gender                   Man 

         Position Title                           Professor 

     Working Department 

    Email                     hanwenyuan@mail.hzau.edu.cn 

   Address 

     Tel                +86-13583776032                   Fax 

Research Interest 

     Prokaryotes are threatened by viral invasion and armed with diverse immune systems, such 
     as CRISPR-Cas, to defeat virus. We want to(1) understand how the immune systems degrade 
     viral  DNA  and/or   RNA  to  protect  host,  (2)  reveal  how the  immune  systems  affect  the 
     competition  between  host  and  virus,  (3)  identify  tool  enzymes  from  prokaryotic  immune 
     systems. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      2011.09 - 2015.05: PhD, Biology, University of Copenhagen, Denmark 

      2008.09 - 2011.07: MSc, Microbiology, Shandong University, China 

      2004.09 - 2008.07: BSc, Ecology, Shandong University, China 

 Professional Experiences: 

      2018.09- present: Professor, Huazhong Agricultural University, China 
﻿     2017.08 - 2018.01: Assistant professor, University of Copenhagen, Denmark 

     2015.08 - 2017.07: Postdoc, University of Copenhagen, Denmark 

Publications 

1.    Tong Guo, Fan Zheng, Zhifeng Zeng, Yang Yang, Qi Li, Qunxin  She, Wenyuan Han*. 

    Cmr3 regulates the suppression on cyclic oligoadenylate synthesis by tag complementarity 

    in a Type III-B CRISPR-Cas system. RNA Biol. 2019 Oct;16(10):1513-1520. 

2.   Wenyuan Han, Stefano Stella, Yan Zhang, Tong Guo, Karolina Sulek, Li Peng-Lundgren, 

    Guillermo   Montoya,  Qunxin   She*.  A Type   III-B Cmr  effector complex   catalyzes  the 

    synthesis  of   cyclic  oligoadenylate  second   messengers    by   cooperative  substrate 

    binding. Nucleic Acids Res. 2018 Nov 2;46(19):10319-10330. 

3.     Tong  Guo, Wenyuan  Han*, Qunxin  She*. Tolerance of  Sulfolobus  SMV 1 virus to the 

    immunity of I-A and III-B CRISPR-Cas systems in Sulfolobus islandicus. RNA Biol. 2019 

    Apr;16(4):549-556. 

4.    Wenyuan Han, Saifu Pan, Blanca Lopez-Mendez, Guillermo Montoya and Qunxin  She. 

    Allosteric regulation of Csx 1, a type IIIB-associated CARF domain ribonuclease by RNAs 

    carrying a tetraadenylate tail. Nucleic Acids Res. 2017 Oct 13;45(18):10740-10750. 

5.   Wenyuan Han, Yingjun Li, Ling Deng, Mingxia Feng, Wenfang Peng, S➢ren Hallstr ➢m, 

    Jing Zhang, Nan Peng, Yun Xiang Liang, Malcolm F. White and Qunxin She. A type III-B 

    CRISPR-Cas effector  complex mediating massive target  DNA  destruction. Nucleic Acids 

    Res. 2017 Feb 28;45(4):1983-1993. 

6.     Wenyuan  Han, Yanqun  Xu, Xu  Feng, Yun  Xiang Liang, Li Huang, Yulong  Shen  and 

    Qunxin  She. NQO-induced DNA-less cell formation  is associated with  chromatin protein 

    degradation  and  dependent  on  A0A 1-ATPase  in  Sulfolobus. Front  Microbiol. 2017  Aug 

     14;8:1480. 

7.    Wenyuan Han, Xu Feng and Qunxin  She. Reverse gyrase functions in genome integrity 

    maintenance by protecting DNA breaks in vivo. Int. J. Mol. Sci. 2017 Jun 22;18(7). 
﻿8.    Wenyuan Han and Qunxin She. CRISPR history: discovery, characterization, application 

    and prosperity. Prog Mol Biol Transl Sci. 2017;152:1-2 1. 

9.     Wenyuan Han, Yulong  Shen  and Qunxin  She. Nanobiomotors of archaeal DNA repair 

    machineries:  current  research status and  application  potential. Cell Biosci. 2014   Jun 

    25;4:32. 

10.   Pengjuan  Liang, Wenyuan  Han, Qihong Huang, Yanze Li, Jinfeng Ni, Qunxin  She and 

    Yulong Shen*. Knockouts of RecA-like proteins RadC 1 and RadC2 have distinct responses 

    to  DNA    damage    agents  in  Sulfolobus  islandicus.  J Genet   Genomics.    2013  Oct 

    20;40(10):533-42. 
﻿                              CURRICULUM VITAE 

Personal Information 

    Name            Jin HE               Gender                    Man 

         Position Title                             Professor 

     Working Department 

    Email                           hej in@mail.hzau.edu.cn 

   Address 

                                                                                          Photo 
     Tel                   86-27-87280670                    Fax 

Research Interest 

     Our   research  interests  include  microbial   functional  genomics,   the  function  of  bacterial 
     nucleotide    second    messenger    molecules     and   non-coding    RNA,     as   well   as   the 
     global    regulation   of  bacterial metabolism.  In   recent  years,  the  research  direction has 
     gradually    expanded    to   include   the   aspects   of   synthetic   biology    and   intestinal 
     microorganisms.      The  main  research  directions  now  include:  (1)  Starting  from  the  basic 
     theoretical  research   on  the  nucleotide   second   messenger   molecules    of  c-di-GMP    and 
     c-di-AMP to reveal their regulatory mechanism on the physiological functions of bacteria to 
     lay  basis  for  the  application  of  beneficial  microorganisms  and  prevention  and  control  of 
     harmful microorganisms; (2)  Studying the regulatory mechanism of non-coding RNA, such 
     as anti-sense RNA, 6S RNA, and tmRNA, to lay the foundation for the transformation and 
     utilization  of bacteria; (3) Developing various synthetic biological regulatory  elements; (4) 
     Studying related intestinal microbial flora and colorectal cancer. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education : 

      09/ 1985-06/ 1989: Bachelor  of  Science  in  Agriculture  (Agricultural  Chemistry)  at 
﻿College of Resources and Environment, 

       Huazhong Agricultural University Wuhan, Hubei, China. 

      09/ 1991-06/ 1994: Master  of  Science  in  Agriculture  (Food  Science)  at  College  of 

Food Science and Technology, 

      Huazhong Agricultural University Wuhan, Hubei, China. 

      09/ 1999-06/2003: Doctor of Science (Microbiology) at College of Life Science and 

Technology, 

       Huazhong Agricultural University Wuhan, Hubei, China. 

Professional Experiences: 

      07/ 1989-08/ 1991: Technician, Wuhan  Shuangfeng  Citric Acid  Co., Ltd., Wuhan, Hubei, 

China. 

      01/2010-Present:       Lecturer, Associate Professor, and Professor (Level 3), College of Life 

Science and Technology, Huazhong Agricultural University, Wuhan, Hubei, China. 

      12/2006-03/2008:        Postdoc/Visiting  Scholar, Department  of Microbiology, University  of 

Illinois at Urbana-Champaign, Illinois, USA. 

Publications 

1.    Wen Yin, Xia Cai, Hongdan  Ma, Li Zhu, Yuling Zhang, Shan-Ho Chou, Michael 

     Galperin, Jin He*. A decade of research on the second messenger c-di-AMP. FEMS 

     Microbiology Reviews, 2020, 44, doi: 10.1093/femsre/fuaa019. 

             #,*           #                          *                   * 
2.   Jin He    , Wen Yin , Michael Y. Galperin , Shan-Ho Chou . Cyclic di-AMP, a second 

     messenger        of     primary      importance:       tertiary     structures      and     binding 

     mechanisms. Nucleic Acids Research, 2020, 48(6):2807–2829. 

                   #             #                                                            * 
3.    Siyang  Xu ,  Wen  Yin ,  Yuling  Zhang,  Qimei  Lv,  Yijun  Yang,  Jin  He .  Foes  or 

     friends?     Bacteria    enriched     in   the    tumor     microenvironment        of    colorectal 

     cancer. Cancers, 2020, 12(2): 00372. 
﻿4.    Cao Zheng, Zhaoqing Yu, Cuiying Du, Yuj ing Gong, Wen Yin, Xinfeng Li, Zhou 

                                                               * 
      Li, Ute  Römling,  Shan-Ho  Chou,  Jin  He . 2-Methylcitrate  cycle:  a  well-regulated 

      controller       of    Bacillus      sporulation.       Environmental           Microbiology,         2020(3): 

      1125– 1140. 

5.     Xun  Wang, Xia Cai, Hongdan  Ma, Wen Yin, Li Zhu, Xinfeng Li, Heon  M. Lim, 

                                       * 
      Shan-Ho       Chou,     Jin   He .  A    c-di-AMP        riboswitch      controlling     kdpFABC         operon 

      transcription        regulates        the     potassium         transporter        system       in     Bacillus 

      thuringiensis. Communications Biology, 2019, 2:151. 

6.    [6]   Yang Fu, Zhaoqing Yu, Shu Liu, Bo Chen, Li Zhu, Zhou Li, Shan-Ho Chou, Jin 

          * 
      He .     C-di-GMP         regulates      various      phenotypes        and     insecticidal      activity     of 

      Gram-positive         Bacillus      thuringiensis.        Frontiers      in   Microbiology,          2018,     9: 

      0045. (recommended as the F 1000Prime paper) 

                     #              # 
7.    Xinfeng Li , Han Mei , Fang Chen, Qing Tang, Zhaoqing Yu, Xiaoj ian Cao, Binda 

                                                                               * 
      Tembeng         Andongma,          Shan-Ho        Chou,       Jin    He .     Transcriptome          landscape 

      of Mycobacterium smegmatis. Frontiers in Microbiology, 2017, 8: 2505. 

8.    Maria Kanwal Ali, Xinfeng Li, Qing Tang, Xiaoyu  Liu, Fang  Chen, Jinfeng Xiao, 

                                                                  * 
      Muhammad          Ali,    Shan-Ho       Chou,     Jin   He .    Regulation       of   inducible     potassium 

      transporter  KdpFABC  by  KdpD/KdpE  two-component                            system  in  Mycobacterium 

      smegmatis. Frontiers in Microbiology, 2017, 8: 570. 

                     #                 #                 # 
9.    Hang Zhou , Cao Zheng , Jianmei Su , Bo Chen, Yang Fu, Yuqun Xie, Qing Tang, 

                                        * 
      Shan-Ho       Chou,     Jin   He .   Characterization        of   a  natural    triple-tandem       c-di-GMP 

      riboswitch         and      application        of     the      riboswitch-based           dual-fluorescence 

      reporter. Scientific Reports, 2016, 6: 20871. 

                                                                                                                      * 
10.   Cao     Zheng,     Yang     Ma,    Xun     Wang,      Yuqun      Xie,    Maria     Kanwal      Ali,   Jin   He . 

      Functional analysis of the sporulation-specific diadenylate cyclase CdaS in Bacillus 

      thuringiensis. Frontiers in Microbiology, 2015, 6: 908. 

11.   Qing Tang, Yunchao Luo, Cao Zheng, Kang Yin, Maria Kanwal Ali, Xinfeng Li, Jin 
﻿          * 
      He .    Functional       analysis     of   a   c-di-AMP-specific           phosphodiesterase         MsPDE 

      from Mycobacterium smegmatis. International Journal of Biological Sciences, 2015, 

      11(7): 813-824. 

12.   Qing  Tang,  Xinfeng  Li,  Tingting  Zou,  Huimin  Zhang,  Yingying  Wang,  Rongsui 

                                       * 
      Gao, Zhencui Li, Jin He , Youjun Feng*. Mycobacteria  smegmatis BioQ defines a 

      new  regulatory  network  for  biotin  metabolism. Molecular  Microbiology,  2014,  94 

      (5): 1006-1023. 

13.   Shumeng  Zhang,  Jieping            Wang,  Yale  Wei,         Qing     Tang,  Maria      Kanwal      Ali,  Jin 

          * 
      He  Heterologous expression of VHb can improve the yield and quality of biocontrol 

      fungus      Paecilomyces         lilacinus,    during      submerged        fermentation.        Journal     of 

      Biotechnology, 2014, 187, 147-153. 

                                                                                                       * 
14.   Jianmei Su, Lin Deng, Liangbo Huang, Shuj in Guo, Fan Liu  and Jin He . Catalytic 

      oxidation  of manganese  (II) by  multicopper  oxidase  CueO  and  characterization  of 

      the biogenic Mn oxide. Water Research, 2014, 56, 304-313. 

15.   Jieping Wang, Han  Mei, Cao Zheng, Hongliang  Qian, Cui  Cui, Yang Fu, Jianmei 

                                                          * 
      Su,    Ziduo     Liu,    Ziniu     Yu,    Jin    He .    The    metabolic       regulation      of   Bacillus 

      thuringiensis  for  the  formation  of  spores  and  parasporal  crystals  revealed  by  the 

      transcriptomics  and  proteomics.  Molecular  and  Cellular  Proteomics,  2013,                         12(5): 

      1363-1376. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name          Jing HE              Gender 

         Position Title                          Professor 

     Working Department 

    Email                       hej ingjj @mail.hzau.edu.cn 

  Address 
                                                                                     Photo 
     Tel                                                 Fax 

Research Interest 

     Biosynthesis, regulation and resistance mechanism of natural products from microorganisms 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      2005.01-2001.11  Doctor    of Science  (Microbiology),   Hans-Knoell-Institute  for Natural 

 Products Research, 

      The University of Jena (Friedrich-Schiller-Universität Jena), Jena, Germany 

      1999.09-2001.06  Master  of  Science  (Molecular  Biology  and  Biochemistry),  College  of 

 Life Science and Technology, 

       Huazhong Agricultural University, Wuhan, China 
﻿      1995.09-1999.06     Bachelor    of  Science   (Biotechnology),     College   of  Life   Science   and 

Technology, 

       Huazhong Agricultural University, Wuhan, China 

Professional Experiences: 

      2008.09-present         Professor,   College    of  Life  Science    and   Technology,    Huazhong 

Agricultural University, Wuhan, China 

      2008.08-2007.09     Postdoctor,    Department     of  Chemistry,    The   University    of  Chicago, 

Chicago, USA 

      2007.03-2005.04 Postdoctor, Kekulé Institute of Organic Chemistry and Biochemistry, 

      The University of Bonn (Rheinische Friedrich-Wilhelms-Universität Bonn), 

Bonn, Germany 

Publications 

1.   Xiaorong Chen, Yuedi Sun, Shan Wang, Kun Ying, Le Xiao, Kai Liu, Xiuli Zuo, Jing He*. 

     Identification of a novel structure-specific endonuclease AziN that contributes to the repair 

     of  azinomycin     B-mediated     DNA      interstrand   crosslinks.  Nucleic    Acids    Res.   2020, 

     48(2):709-718. 

2.    Qin Liu, Qin Lin, Xinying Li, Muhammad Ali, Jing He*. Construction and application of a 

     "superplasmid" for  enhanced production  of antibiotics. Appl Microbiol Biotechnol. 2020, 

     104(4):1647-1660. 

3.        Mengyi  Zhu,  Lijuan  Wang,  Jing  He*.  Chemical  diversification  based  on           substrate 

     promiscuity  of  a  standalone  adenylation  domain  in  a  reconstituted  NRPS  system.  ACS 

     Chem Biol. 2019, 14(2):256-265. 

                          #                 # 
4.         Mengyi  Zhu  ,  Lijuan    Wang ,  Qingbo  Zhang,  Muhammad  Ali,            Siqi  Zhu,  Peiqing 

     Yu,   Xiaofei    Gu,   Haibo    Zhang,    Yiguang     Zhu,    Jing   He*.   Tandem      hydration    of 

     diisonitriles triggered  by  isonitrile hydratase  in  Streptomyces thioluteus. Org  Lett. 2018, 
﻿     20(12):3562-3565. 

                     #               # 
5.    Lijuan Wang , Mengyi Zhu , Qingbo Zhang, Xu Zhang, Panlei Yang, Zihui Liu, Yun Deng, 

     Yiguang Zhu, Xueshi Huang, Li Han, Shengqing Li, Jing He*. Diisonitrile natural product 

     SF2768     functions   as  a  chalkophore     that  mediates    copper   acquisition   in  Streptomyces 

     thioluteus. ACS Chem Biol. 2017, 12(12):3067-3075. 

6.    Shan Wang, Kai Liu, Le Xiao, LiYuan Yang, Hong Li, FeiXue Zhang, Lei Lei, ShengQing 

     Li, Xu Feng, AiYing Li, Jing He*. Characterization of a novel DNA glycosylase from  S. 

     sahachiroi    involved    in   the  reduction     and   repair   of  azinomycin      B   induced     DNA 

     damage. Nucleic Acids Res. 2016, 44(1):187-197. 

7.       Ying  Zhai,  Silei  Bai,  Jingj ing  Liu,  Liyuan  Yang,  Li  Han,  Xueshi  Huang,  Jing  He*. 

     Identification    of  an  unusual    type   II  thioesterase   in  the   dithiolopyrrolone     antibiotics 

     biosynthetic pathway. Biochem Biophys Res Commun. 2016, 473(1):329-335. 

8.    Shan Wang, Ruifang Zhao, Kai Liu, Mengyi Zhu, Aiying Li, Jing He*. Essential role of an 

     unknown  gene  aziU3 in  the production  of  antitumor  antibiotic  azinomycin  B  verified by 

     utilizing  optimized     genetic   manipulation     systems    for  Streptomyces     sahachiroi.   FEMS 

     Microbiol Lett. 2012, 337(2):147-154. 

9.      Sheng Huang, Yudong Zhao,Zhiwei Qin, Xiaoling Wang, Mayca Onega, Li Chen, Jing 

     He*, Yi Yu*, Hai  Deng*. Identification  and heterologous  expression  of the biosynthetic 

     gene cluster for holomycin produced by Streptomyces clavuligerus. Process Biochemistry. 

     2011, 46(3):811-816. 

10.    Jing  He  and  Christian  Hertweck.  Functional  analysis  of  the  aureothin  iterative  type  I 

     polyketide synthase. ChembioChem. 2005, 6(5):908-912. 

11.   Jing He, Markus Müller, Christian Hertweck*. Formation of the aureothin tetrahydrofuran 

     ring    by    a    bifunctional     cytochrome       P450      monooxygenase.         J.   Am.     Chem. 

     Soc. 2004, 126(51):16742-16743. 

12.    Jing  He,  Christian  Hertweck*. Biosynthetic  origin  of  the  rare  nitro  aryl  moiety  of  the 

     polyketide antibiotic aureothin: discovery of an unprecedented N-oxygenase. J. Am. Chem. 
﻿    Soc. 2004, 126(12):3694-3695. 

13.    Jing  He  and  Christian Hertweck*.  Iteration as  programmed event during  polyketide 

    assembly;  molecular  analysis of the  aureothin biosynthesis gene  cluster. Chem.  Biol. 

    2003, 10(12):1225-1232. 
﻿                            CURRICULUM VITAE 

Personal Information                                                                  Photo 

    Name     Yonggang Hu               Gender                  male 

         Position Title                           Professor 

     Working Department           College of Life Science and Technology 

    Email                    yongganghu@mail.hzau.edu.cn 

              State Key Laboratory of Agricultural Microbiology, College of 
  Address          Life Science and Technology, Huazhong Agricultural 
                            University, Wuhan 430070, China 
     Tel                  027-87280670                    Fax               027-87280670 

Research Interest 

     Applied Microbiology, Biosensor 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 B.S., Wuhan University, 1987-1991 

 M.S., Wuhan University, 1991-1994 

 Ph.D., Wuhan University, 1994-1997 

 Postdoctor, State key laboratory of physical chemistry of solid surfaces, 1997-2000 

 Associate Professor, School of environmental science and engineering, Huazhong university of 

 science and technology, 2000-2005 

 Professor,  School  of  environmental  science  and  engineering, Huazhong university  of  science 

 and technology, 2005-2008. 

 Professor,  National  Key   Laboratory  of  Agricultural  Microbiology,   Huazhong    Agricultural 
﻿University, College of Life Science and Technology, Huazhong Agricultural University. 2008- 

Publications 

[1] Y. Qin, W. Ke, A.  Faheem, Y. Ye,  Y.  Hu, A  rapid  and  naked-eye  on-site  monitoring  of 

biogenic amines in foods spoilage, Food Chem, 404(2023) 134581. 

[2] Y. Qin, Y. Li, Y. Hu, Emerging Argonaute-based nucleic acid biosensors, Trends Biotechnol, 

40(2022) 910-914. 

[3] F. Peng, Y. Xiang, H. Wang, Y. Hu, R. Zhou, Y. Hu, Biomimetic assembly of spore@ZIF-8 

microspheres for vaccination, Small, 18(2022) e2204011. 

[4] Y. Xiang, H. Yan, B. Zheng, A. Faheem, A. Guo,  C. Hu, Y. Hu, Light-regulated  natural 

fluorescence of the PCC 6803@ZIF-8 composite as an encoded microsphere for the detection of 

multiple biomarkers, ACS sensors, 6(202 1) 2574-2583. 

[5] Y. Xiang, H. Yan, B. Zheng, A. Faheem, W. Chen, Y. Hu, E. coli@UiO-67 composites as a 

recyclable adsorbent for bisphenol A removal, Chemosphere, 270(202 1) 128672. 

[6] Y. Qin, A. Faheem, Y. Hu, A spore-based portable kit for on-site detection of fluoride ions, J 

Hazard Mater, 4 19(202 1) 126467. 

[7] A. Faheem, Y. Qin, W. Nan, Y. Hu, Advances in the Immunoassays for Detection of Bacillus 

thuringiensis Crystalline Toxins, J Agric Food Chem, 69(202 1) 10407-104 18. 

[8] Y. Xiang, H. Yan, B. Zheng, A. Faheem, Y. Hu, Microorganism@UiO-66-NH2 Composites 

for  the  Detection  of  Multiple  Colorectal  Cancer-Related  microRNAs  with  Flow  Cytometry, 

Anal Chem, 92(2020) 12338-12346. 

[9] X. Sun, Y. Wang, L. Zhang, S. Liu, M. Zhang, J. Wang, B. Ning, Y. Peng, J. He, Y. Hu, Z. 

Gao,  CRISPR-Cas9 triggered  two-step  isothermal  amplification  method  for  E.  coli  O157:H7 

detection based on a Metal-Organic Framework platform, Anal Chem, 92(2020) 3032-304 1. 

[10]  X.  Sun,  R.  Fei,  L.  Zhang,  B.  Huo,  Y.  Wang,  Y.  Peng, et al.,  Bio-barcode triggered 

isothermal amplification  in  a fluorometric competitive immunoassay  for the phytotoxin  abrin, 

Microchim Acta, 187(2020) 127. 

[11] Y. Qin, G. Wu, Y. Guo, D. Ke, J. Yin, D. Wang, X. Fan, Z. Liu, L. Ruan, Y. Hu, Engineered 

glyphosate oxidase coupled to spore-based chemiluminescence system for glyphosate detection, 
﻿Anal Chim Acta, 1133(2020) 39-47. 

[12]  Y. Qin,  A.  Faheem,    G.  Jia, Y. Hu,   Self-assembled   Fe3+@spores   as  a  sustainable 

heterogeneous Fenton catalyst for arsenite removal, J Environ Chem Eng, 8(2020) 104485. 

[13] F. Peng, B. Zheng, Y. Zhang, A. Faheem, Y. Chai, T. Jiang, X. Chen, Y. Hu, Biocatalytic 

oxidation  of  aromatic  compounds  by  spore-based  system, ACS  Sustain  Chem  Eng,  8(2020) 

14 159-14 165. 
﻿                             CURRICULUM VITAE 

Personal Information 

    Name           Shan LI              Gender                 Famale 

         Position Title                            Professor 

     Working Department             Collage of Life Science & Technology 

    Email                         lishan@mail.hzau.edu.cn 

   Address 

     Tel                                                   Fax 

Research Interest 

     1.  molecular mechanisms of pathogenic microorganism-host interactions; 
     2. Development of human immune disease treatment methods based on bacterial protein; 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 2017-present. Prof. Collage of Life Science & Technology. Huazhong Agricultural University 
 2015-2017.  Director, Institute  of  Infectious  and  Immune  Diseases,  Taihe  Hospital  of  Shiyan 
 City, Hubei Province 
 2013-2015.    Postdoc.Biochemistry    and  Molecular    Biology.  Beij ing Institute of  Biological 
 Sciences 
 2007-2013. Ph.D. Biochemistry and Molecular Biology. Beij ing Institute of Biological Sciences 
 2003-2007. B.A. Crop genetics and breeding. China Agricultural University 

 Publications 
﻿1.  Peng  T*, Tao X*, Xia  Z,  Hu  S, Xue  J, Zhu  Q, Pan  X, Zhang  Q,  Li  S. (2022)  Pathogen 

Hij acks  Programmed     Cell  Death   Signaling  by  Arginine  ADPR-Deacylization         of Caspases. 

Molecular Cell. 

2.  Peng  T*, Tao X*, Xia  Z,  Hu  S, Xue  J, Zhu  Q, Pan  X, Zhang  Q,  Li  S. (2022)  Pathogen 

Hij acks  Programmed     Cell  Death   Signaling  by  Arginine  ADPR-Deacylization         of Caspases. 

Molecular Cell. 

3.  Zhang K*, Peng T*, Tao X*, Tian M*, Li Y, Wang Z, Ma S, Hu S, Pan X, Xue J, FuY#, Li 

S#. Structural  insights into  caspase ADPR-deacylization  catalyzed by  a bacterial  effector  and 

host calmodulin. Molecular Cell in revision 

4.  Xue  J, Huang Y, Zhang  H, Hu  J, Pan  X, Peng  T, Lv  J, Meng  K, Li  S#. (2022) Arginine 

Glcnacylation  and  Activity  Regulation  of  Phop  by  a  Type  Iii  Secretion     System  Effector  in 

Salmonella. Frontiers in Microbiology. 

5.  Lv J* ，Yang J*，Xue J ，Li S#. (2020) Detection of SARS-CoV-2 RNA residue on obj ect 

surfaces  in  nucleic  acid  testing  laboratory  using  droplet  digital  PCR.  Science  of  The  Total 

Environment 
﻿                             CURRICULUM VITAE 

Personal Information 

    Name           Zhu LIU              Gender                    Man 

         Position Title                             Professor 

     Working Department 

    Email                          liuzhu@mail.hzau.edu.cn 

   Address                                                                               Photo 

     Tel                                                    Fax 

Research Interest 

     I  am  interested  in  protein  dynamics  and  enzymatic  mechanisms.  By  using  an  integrative 
     strategy  with  multiple  biophysical   tools, including   single-molecule   fluorescence,  NMR, 
     crystallography,  chemical  cross-linking  coupled  with  mass  spectroscopy,  and  small-angle 
     X-ray  scattering,  my  research  characterized  the  functional  roles  of  protein  dynamics  and 
     added insights into the mechanisms underlying enzyme catalysis. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      2009 - 2014 ：Wuhan Institute of Physics and Mathematics, Chinese Academy of Sciences, 
      Ph.D. 

      2005 - 2009 ：College of Chemistry and Molecular Sciences, Wuhan University, B.S. 

 Professional Experiences: 

      2018 - present: Professor 

      College of Life Science and Technology, Huazhong Agricultural University, National Key 
      Laboratory of Crop Genetic Improvement, Wuhan, China. 
﻿      2017 - 2018：Assistant Professor 

      Wuhan  Institute  of  Physics  and  Mathematics,  Chinese  Academy                          of   Sciences     ,  Wuhan, 
      China. 

      2014 - 2017 ：Postdoctoral fellow 

      School of Medicine, Zhej iang University, Hangzhou, China. 

Publications 

                      #            #                            * 
1.          Zhou  C ,  Yan  L ,  Zhang  WH,  Liu  Z .  Structural  basis  of  tubulin  detyrosination  by 

      VASH2/SVBP heterodimer. Nature Communications. 2019, 10(1):32 12. 

                   #             #                                                                                *            * 
2.         Liu  Z , Dong  X , Yi  HW, Yang  J,  Gong  Z,  Wang  Y,  Liu  K, Zhang  WP ,  Tang  C . 

      Structural     basis   for   the   recognition      of   K48-linked       Ub    chain    by   proteasomal       receptor 

      Rpn 13. Cell Discovery. 2019, 5:9. 

                                                                                                           * 
3.     Liu Z, Gong Z, Cao Y, Ding YH, Dong MQ, Lu YB, Zhang WP, Tang C . Characterizing 

      Protein       Dynamics          with       Integrative        Use       of      Bulk       and       Single-Molecule 

      Techniques. Biochemistry. 2018, 57:305-313. 

                 #            #                                                                        *               * 
4.     Dong X , Gong Z , Lu YB, Liu K, Qing LY, Ran ML, Zhang CL, Liu Z , Zhang WP , Tang 

        * 
      C . Ubiquitin  S65 phosphorylation  engenders a pH-sensitive  conformational  switch. Proc 

      Natl Acad Sci, USA. 2017, 114:6770-6775. 

                                                         * 
5.      Liu Z, Gong Z, Dong X and Tang C . Transient protein-protein interactions visualized by 

      solution NMR. BBA Proteins and Proteomics. 2016, 1864:115-122. 

                                                                                                              *                * 
6.     Liu Z, Gong Z, Jiang WX, Yang J, Zhu WK, Guo DC, Zhang WP, Liu ML                                       and Tang C . 

      Lys63-linked       ubiquitin     chain    adopts     multiple     conformational        states   for   specific    target 

      recognition. 2015, Elife,4:e05767. 

                                                            *                 * 
7.       Liu Z, Gong Z, Guo DC, Zhang WP                      and Tang C . Subtle dynamics of holo glutamine 

      binding     protein     revealed     with    a   rigid   paramagnetic        probe.     Biochemistry.        2014,     53, 

      1403-1409. 

                                                                      *                * 
8.      Liu Z, Zhang WP, Xing Q, Ren XF, Liu ML                        and Tang C . Noncovalent dimerization of 
﻿ubiquitin. 2012, Angew Chem Int Ed, 51, 469-472. (hot paper). 
﻿                              CURRICULUM VITAE 

Personal Information 

    Name        Xingwang LI              Gender 

         Position Title                             Professor 

     Working Department 
                                                                                          Photo 
    Email                       xingwangli@mail.hzau.edu.cn 

                  National Key Laboratory of Crop Genetic Improvement 
                          College of Life Science and Technology 
   Address 
                              Huazhong Agricultural University 
                                    Wuhan 430070, China. 
     Tel                                                     Fax 

Research Interest 

     The linear genome of higher organisms are known to be folded into chromosomal territories 
     within the three-dimensional (3D) nuclear. Recent achievements on 3D genome organization 
     have revealed  frequent  chromatin  loops within topological-associated domains (TADs) and 
     have   implicated   general  mechanism     of  chromatin   loops   between   gene   promoters   and 
     enhancers  for  transcriptional  regulation. Rice  (Oryza  sativa)  is  one  of  the  most  important 
     food crops in the world and has been established as a model plant for biological research. To 
     explore  3D   genome    structures  and  its  dynamic  (4D)  in  rice,  we  have  been  focused  on 
     developing    plants  3D  genome    mapping    technologies   and   exploring  mechanism     of  3D 
     genome    structure  on  transcription  regulation  since  2013.  More   specifically,  we  applied 
     cutting-edge 3D genome mapping technologies and characterized genome-wide DNA-DNA, 
     RNA-DNA interactions mediated by  active gene promoters and heterochromatin  at various 
     developmental  stages  and  examined  the  comprehensive  hierarchical  3D  genome  structure 
     and their dynamics as well as their impacts on transcriptional regulation. 

Professional Memberships 

Other Roles 

 Education & Working Experience 
﻿Education 

    2003-09 to 2011-06: PhD in Biochemistry and Molecular Biology, Huazhong Agricultural 
    University, Wuhan, China, Supervisor: Qifa Zhang, Changyin Wu 

     1999-09 to 2003-07: B.S. Biotechnology, Inner Mongolia Agricultural University, Huhhot, 
    China 

Research and work experience 

    2016-08  to  present ：Professor  in  Genomcis,  College  of  Life  Science  and  Technology, 
    Huazhong Agricultural University, Wuhan, China 

    2013-07  to  2016-07 ：Post  Doctorate,  The  Jackson  Laboratory  for  Genomic  Medicine, 
    Connecticut, USA 

    2011-07   to  2013-06:  Research   Associate,  National  Key   Laboratory   of Crop   Genetic 
    Improvement, Wuhan, China 

Publications 

1.  Qin Xiao*, Xingyu  Huang*, Yan Zhang, Wei Xu, Yongqing Yang, Qing Zhang, Zhe Hu, 

    Feng Xing, Qianwen  Sun, Guoliang Li, Xingwang Li. The landscape of promoter-centered 

    RNA-DNA interactions in rice. Nature Plants, 2022, 157– 170. 

2.  Li  Deng*,  Baibai  Gao*,  Lun  Zhao,  Ying  Zhang,  Qing  Zhang,  Guoting  Chen,  Shuangqi 

    Wang,    Liang   Xie,  C.  Robertson    McClung,    Guoliang    Li,  Xingwang    Li.  Diurnal 

    RNAPII-tethered  chromatin  interactions  are  associated  with  rhythmic  gene  expression  in 

    rice. Genome Biology, 2022, 23: 7. 

3.  Weizhi   Ouyang*,    Shiping  Luan*,   Xu   Xiang,  Minrong    Guo,   Yan   Zhang,  Guoliang 

    Li,  Xingwang   Li.  Profiling  Plant Histone  Modification at  Single-cell Resolution.  Plant 

    Biotechnology Journal, 2022, 20: 420–422. 

4.  Lun Zhao*, Shuangqi Wang*, Zhilin Cao*, Weizhi Ouyang, Qing Zhang, Liang Xie, Ruiqin 

    Zheng,   Minrong   Guo,   Meng   Ma,   Zhe   Hu,  Wing-Kin    Sung,   Qifa  Zhang,  Guoliang 

    Li#,  Xingwang  Li#.  Chromatin  loops  associated  with  active  genes  and  heterochromatin 

    shape     rice    genome      architecture    for    transcriptional    regulation.    Nature 

    Communications, 2019, 10: 3640. 

5.  Zhonghui   Tang*,   Oscar  Luo*,  Xingwang    Li*,  Meizhen   Zheng,  Jacqueline  Jufen  Zhu, 
﻿    Przemyslaw    Szalaj , Pawel  Trzaskoma,   Adriana   Magalska,   Jakub  Wlodarczyk,   Blazej 

    Ruszczycki, Paul Michalski, Emaly Piecuch, Ping Wang, Danjuan Wang, Simon Zhongyuan 

    Tian, Xiaoan Ruan, May Penrad-Mobayed, Laurent M. Sachs, Chia-Lin Wei, Edison T. Liu, 

    Grzegorz M. Wilczynski, Dariusz Plewczynski, Guoliang Li, Yijun Ruan. CTCF-mediated 

    3D    genome      architecture   reveals   a    chromatin     topology    for   transcription 

    regulation. Cell, 2015, 163: 1611– 1627. 

6.  YongPeng,   DanXiong,    LunZhao,   WeizhiOuyang,     ShuangqiWang,    JunSun,   QingZhang, 

    PengpengGuan,     LiangXie,    WenqiangLi,     GuoliangLi,   JianbingYan,    Xingwang     Li, 

    Chromatin interaction m aps reveal genetic regulation for quantitative traits in maize, Nature 

    Communications, 2019,10: 2632 

7.  Weizhi   Ouyang,   DanXiong,   Guoliang   Li,  Xingwang    Li, Unraveling   the 3D   genome 

    architecture in plants: present and future, Molecular Plant, 2020,13:1676-1693 

8.  WeizhiOuyang,    QinXiao,   GuoliangLi,   Xingwang    Li,  Technologies   for  capturing  3D 

    genome architecture in plants, Trends in Plant Science, 202 1,26:196-197 

9.  LiangXie,      MinghaoLiu,        LunZhao,        KaiCao,       PengWang,        WenhaoXu, 

    Wing-KinSung, Xingwang  Li,  GuoliangLi,  RiceENCODE: A  comprehensive  epigenomic 

    database as a rice Encyclopedia of DNA Elements, Molecular Plant,202 1,14:1604-1606 

10. WeizhiOuyang,  XiwenZhang,  YongPeng,  QingZhang,  ZhilinCao,  GuoliangLi,  Xingwang 

    Li,    Rapid   and   low-input   profiling  of  histone  marks   in  plants   using  nucleus 

    CUT&Tag, Frontiers in Plant Science,202 1,12:634679 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name         Youguo LI             Gender                  male 

         Position Title                          Professor 

     Working Department            Collage of Life Science & Technology 

    Email                       youguoli@mail.hzau.edu.cn 

  Address 

     Tel                                                 Fax 

Research Interest 

     Molecular mechanism and application of rhizobia symbiotic nitrogen fixation system 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 2007-present.  Professor.  College  of Life  Science  and  Technology,   Huazhong  Agricultural 
 University 
 2000-2007.   Associate   Professor.  College   of  Life  Science   and  Technology,    Huazhong 
 Agricultural University 
 2002-2005. Postdoc. School of Life Sciences, East Anglia University, UK 
 2001-2001. Visiting  Scholar. Laboratory  of  Microbial  and  Molecular  Ecology, University  of 
 Wageningen, The Netherlands 
 1994-2001.   Lecturer,  College   of  Life  Science  and   Technology,   Huazhong    Agricultural 
 University 
 1991-1994. Lecturer, Department of Soil Agrochemistry. Huazhong Agricultural University 
 1988-1991. M.A. Cell Biology. Collage of Biology. Wuhan University 
 1984-1988.B.A. Cell Biology. Collage of Biology. Wuhan University 

 Publications 
﻿1.   Jianyun Wang, Zaiyong Si, Fang Li, Xiaobo Xiong, Lei Lei, Fuli Xie, Dasong Chen, Yixing 

Li*,  Youguo  Li*  (2015).  A  purple  acid  phosphatase  plays  a  role  in  nodule  formation and 

nitrogen fixation in Astragalus sinicus. Plant Molecular Biology, 88 (6): 515-29. 

2.  Lei, L., L. Chen, X. Shi, Y. Li, J. Wang, D. Chen, F. Xie and Y. Li* (2014). A nodule-specific 

lipid transfer protein AsE246 participates in transport of plant-synthesized lipids to symbiosome 

membrane and is essential for nodule organogenesis in Chinese milk vetch. Plant Physiol  164 

(2): 1045-1058. 

3.  Shanming Wang, Baohai Hao, Jiarui Li, Jieli Peng, Fuli Xie, Xinyin Zhao, Christian Frech, 

Nansheng    Chen*,    Binguang    Ma*,   Youguo    Li*   (2014).  Whole-genome      sequencing    of 

Mesorhizobium huakuii 7653R provides molecular insights into host specificity and symbiosis 

island dynamics. BMC Genomics, 15: 440. 
﻿                              CURRICULUM VITAE 

Personal Information 

    Name       Ouyang YIDAN              Gender                  Woman 

         Position Title                             Professor 

     Working Department 

    Email                     diana198394 1@mail.hzau.edu.cn 

   Address     National Key Laboratory of Crop Genetic Improvement C502 

     Tel                   86-27-87281677                    Fax 

Research Interest 

     Genetic    differentiation  between    the  subspecies/species    results  in  various   forms    of 
     reproductive barriers. Such  genetically based barriers lead to reproductive isolation, which 
     prevent  gene  flow between  populations. Reproductive  isolation  is both  the indicator  and  a 
     primary  force  of  speciation, playing  a key  role  in  maintaining  species  identity. The maj or 
     interest  is  reproductive  isolation  and  population  differentiation  in  rice,  which  is  in  close 
     relationship with utilization of heterosis in hybrid rice. The research areas include functional 
     genomics, evolution and population genetics. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

       Sep 2003 - Dec 2008 Ph. D. Biochemistry and Molecular Biology, College of Life Science 

 and Technology, Huazhong Agricultural University, Wuhan, China. 

       Sep   1999   -  Jun   2003   B.  S.  Biological    Science,   College   of  Life   Science   and 

 Technology, Huazhong Agricultural University, Wuhan, China. 

       Sep  1999 - Jun  2003 B. A. English, English  Department, College  of Foreign  Language, 
﻿Huazhong University of Science and Technology, Wuhan, China. 

Positions Held: 

     Nov   2015  –  present  Professor, College   of Life  Science  and  Technology,   Huazhong 

Agricultural University, Wuhan, China. 

     Jan  2013  –  Nov  2015  Associate  Professor,  College  of  Life Science  and  Technology, 

Huazhong Agricultural University, Wuhan, China. 

     Mar   2012  - Mar   2013  Visiting  Scholar,  Department   of  Ecology  and  Evolution,  The 

University of Chicago, Chicago, USA 

     Mar   2011  -  June  2014  Research  Associate,  National  Key  laboratory of  Crop  Genetic 

Improvement, Huazhong Agricultural University, Wuhan, China. 

     Mar   2009  -  Dec 2012  Lecturer,  College  of  Life Science   and Technology,  Huazhong 

Agricultural University, Wuhan, China. 

Publications 

1.   欧阳亦聃，程祝宽，张大兵                    （2019 ）中国学科发展战略：作物功能基因组学，第 10 

     章作物生殖发育功能基因组研究，科学出版社                                （北京） 

2.   Ouyang Y, Understanding and breaking down the reproductive barrier between Asian 

     and African cultivated rice: a new start for hybrid rice breeding (2019) Sci China Life Sci, 

     62: doi.org/ 10.1007/s11427-019-9592-6 

3.   Li G, Jin J, Zhou Y, Bai X, Mao D, Tan C, Wang G, Ouyang Y, Genome-wide dissection 

     of segregation  distortion using multiple inter-subspecific crosses in rice (2019)  Sci China 

    Life Sci, 62(4): 507-516 

4.    Zhang L*, Ren Y*, Yang T, Li G, Chen J, Gschwend AR, Yu Y, Hou G, Zi J, Zhou R, 

    Wen B, Zhang J, Chougule K, Wang M, Copetti D, Peng Z, Zhang C, Zhang Y, Ouyang Y, 

    Wing    RA,   Liu  S,  Long   M    (2019)  Rapid   evolution  of protein  diversity by   de 

    novo origination in Oryza. Nat Ecol Evol 3 (4):679-690 
﻿     2018 

5.     Sun  S, Wang L, Mao H,  Shao L, Li X, Xiao J, Ouyang Y, Zhang  Q, A  G-protein 

    pathway   determines   grain size  in rice  (2018)  Nature Communications,  9:  851,  F 1000 

    recommendation 

6.      Yao  W,  Li  G, Yu  Y,  Ouyang  Y    (2018)  funRiceGenes  dataset  for  comprehensive 

    understanding and application of rice functional genes. GigaScience 7(1): 1-9 

7.    Yu Y, Ouyang Y, Yao W         (2018) shinyCircos: an R/Shiny application for interactive 

    creation of Circos plot. Bioinformatics 34(7): 1229-1231 

8.    Ouyang Y, Zhang Q, The molecular and evolutionary basis of reproductive isolation in 

    plants (2018) J Genet Genomics 45: 613-620 

9.     Guo J*, Xu  C*, Wu  D*, Zhao Y, Qiu  Y, Wang X, Ouyang Y, Cai B, Liu  X, Jing  S, 

     Shangguan X, Wang H, Ma Y, Hu L, Wu Y, Shi S, Wang W, Zhu L, Xu X, Chen R, Feng 

    Y, Du  B, He  G     (2018) Bph6 encodes an  exocyst-localized protein  and confers broad 

    resistance to planthoppers in rice. Nature Genetics 50: 297-306 

10.  Zhu C, Peng Q, Fu D, Zhuang D, Yu Y, Duan M, Xie W, Cai Y, Ouyang Y, Lian X, Wu 

    C   (2018)  The  E3 ubiquitin  ligase  HAF 1 modulates  circadian  accumulation  of  EARLY 

    FLOWERING3  to  control  heading  date  in  rice under  long-day  conditions. Plant  Cell  30 

    (10):2352-2367 

     2017 

11.  Li G*; Li X*; Wang Y; Mi J; Xing F; Zhang D; Dong Q; Li X; Xiao J; Zhang Q; Ouyang 

    Y   (2017)   Three  representative inter and   intra-subspecific crosses reveal  the  genetic 

    architecture of reproductive isolation in rice. Plant Journal 92(3): 349-362, Cover Story 

12.     Sheila McCormick     (2017)  Discovery   of  new  QTLs  underlying   hybrid  fertility and 

    reproductive isolation in rice. Plant Journal 92(3): 347-348, RESEARCH HIGHLIGHT for 

    our work 

13.   Zhu  Y, Yu  Y,  Cheng  K, Ouyang  Y, Wang  J,  Gong  L, Zhang  Q, Li  X, Xiao  J, Zhang 
﻿     Q   (2017)  Processes  underlying    a  reproductive  barrier  in indica-j aponica  rice  hybrids 

    revealed by transcriptome analysis. Plant Physiology 174(3): 1683-1696 

     2016 

14.  Ouyang Y*, Li G*, Mi J*, Xu C, Du H, Zhang C, Xie W, Li X, Xiao J, Song H, Zhang Q 

     (2016)  Origination  and  establishment  of  a  trigenic  reproductive  isolation  system  in  rice. 

    Molecular Plant 9(11): 1542-1545 

15.  Mi J ，Li G，Huang J ，Yu H ，Zhou F ，Zhang Q，Ouyang Y ，Mou T  (2016) Stacking S5-n 

     and  f5-n to  overcome    sterility in indica-j aponica  hybrid  rice.  Theoretical  and  Applied 

     Genetics 129(3): 563-575 

16.  Zhang JW*, Chen LL*, Xing F*, Kudrna DA, Yao W, Copetti D, Mu T, Li WM, Song JM, 

    Xie WB, Lee S, Talag J, Shao L, An Y, Zhang CL, Ouyang Y, Sun S, Jiao WB, Lv F, Du 

    BG, Luo MZ, Maldonado CE, Goicoechea JL, Xiong LZ, Wu CY, Xing YZ, Zhou DX, Yu 

     SB, Zhao  Y, Wang  GW, Yu  YS, Luo  YJ, Zhou  ZW, Hurtado  BEP, Danowitz  A, Wing 

    RA, Zhang QF        (2016) Extensive sequence divergence between the reference genomes 

    of two elite indica rice varieties Zhenshan 97 and Minghui 63. Proc Natl Acad Sci U  S A 

     113(35): E5163-E5171 

17.  Zhao Y*, Huang J*, Wang Z*, Jing S, Wang Y, Ouyang Y, Cai B, Xin XF, Liu X, Zhang 

     C, Pan Y, Ma R, Li Q, Jiang W, Zeng Y, Shangguan X, Wang H, Du B, Zhu L, Xu X, Feng 

    YQ,    He   SY,   Chen    R,  Zhang    Q,   He    G   (2016)   Allelic   diversity  in  an  NLR 

    gene  BPH9  enables  rice  to  combat  planthopper  variation.  Proc  Natl  Acad       Sci  U  S  A 

     113(45): 12850-12855 

     2015 

18.  Zhao H, Yao W, Ouyang Y, Yang W, Wang G, Lian X, Xing Y, Chen L, Xie W  (2015) 

    RiceVarMap : a comprehensive database of rice genomic variations. Nucleic Acids Res 43 

     (D 1):D 1018-D 1022 

     2014 

19.   Niu  S*, Yu  Y*, Xu  C, Li  G, Ouyang Y        (2014)  Prezygotic reproductive isolation  and 
﻿     fertility in crosses between indica and j aponica subspecies. Sci China Ser C-Life Sci 44(8): 

     815-82 1 

20.    Zhang  C,  Gschwend  AR,  Ouyang  Y,  Long  M        (2014)  Evolution  of  gene  structural 

     complexity: an alternative-splicing-based model accounts for intron-containing retrogenes. 

    Plant Physiol 165: 4 12-423 

     2013 

2 1.   Ouyang  Y,  Zhang  Q    (2013)  Understanding  reproductive  isolation  based  on  the  rice 

    model. Annu Rev Plant Biol 64: 111-135 

22.   Lu Z, Huang X, Ouyang Y, Yao J         (2013) Genome-Wide Identification, Phylogenetic 

     and Co-Expression Analysis of OsSET Gene Family in Rice. PloS one 8: e65426 

23.   Huang J, Zhao X, Cheng K, Jiang Y, Ouyang Y, Xu  C, Li X, Xiao J, Zhang Q            (2013) 

     OsAP65, a rice  aspartic protease, is essential  for male fertility  and plays a role in pollen 

     germination and pollen tube growth. Journal of experimental botany 64: 3351-3360 

     2012 

24.   Ouyang Y*, Huang X*, Lu  Z, Yao  J        (2012)  Genomic  survey,  expression  profile  and 

     co-expression network analysis of OsWD40 family in rice. BMC Genomics 13: 100 

25.  Yang J*, Zhao X*, Cheng K*, Du H, Ouyang Y, Chen J, Qiu S, Huang J, Jiang Y, Jiang L, 

    Ding J, Wang J, Xu  C, Li X, Zhang  Q       (2012) A  killer-protector  system  regulates both 

    hybrid sterility and segregation distortion in rice. Science 337: 1336-1340 

26.  Ding J, Lu Q, Ouyang Y, Mao H, Zhang P, Yao J, Xu C, Li X, Xiao J, Zhang Q  (2012) A 

     long noncoding RNA regulates photoperiod-sensitive male sterility, an essential component 

     of hybrid rice. Proc Natl Acad Sci U S A 109: 2654-2659 

     2011 

27.    Du  H*,  Ouyang  Y*,  Zhang  C,  Zhang  Q     (2011)  Complex  evolution  of  S5,  a  maj or 

    reproductive barrier regulator, in the cultivated rice Oryza sativa and its wild relatives. New 

    Phytol 191: 275-287 
﻿28.    Li  X,  Gao  X,  Wei  Y,  Deng  L,  Ouyang  Y,  Chen  G,  Zhang  Q,  Wu  C    (2011)  Rice 

    APOPTOSIS          INHIBITOR5         coupled     with      two     DEAD-box         adenosine 

     5'-triphosphate-dependent  RNA  helicases  regulates  tapetum  degeneration.  Plant  Cell  23: 

     14 16-1434 

     2010 

29.  Ouyang Y, Liu YG, Zhang Q  (2010) Hybrid sterility in plant: stories from rice. Curr Opin 

    Plant Biol 13: 186-192 

     2009 

30.   Ouyang  Y,  Chen  J, Xie  W, Wang  L,  Zhang  Q  (2009)  Comprehensive  sequence  and 

     expression profile analysis of Hsp20 gene family in rice. Plant Mol Biol 70: 34 1-357 

31.     Ouyang   Y,  Chen   J, Ding  J,  Zhang  Q   (2009)  Advances    in the  understanding   of 

     inter-subspecific hybrid  sterility and wide-compatibility   in  rice. Chinese  Sci  Bull  54: 

    2332-234 1 

32.  Chen J*, Ouyang Y*, Wang L, Xie W, Zhang Q  (2009) Aspartic proteases gene family in 

    rice: Gene  structure  and  expression, predicted protein  features  and phylogenetic relation. 

     Gene 442: 108-118 

     2008 

33.  Chen J*, Ding J*, Ouyang Y*, Du H, Yang J, Cheng K, Zhao J, Qiu  S, Zhang X, Yao J, 

    Liu K, Wang L, Xu C, Li X, Xue Y, Xia M, Ji Q, Lu J, Xu M, Zhang Q  (2008) A triallelic 

     system  of  S5   is a  maj or  regulator  of  the  reproductive   barrier  and  compatibility 

     of indica-j aponica hybrids in rice. Proc Natl Acad Sci U S A 105: 11436-1144 1 

     2004 

34.    Chu  Z*,  Ouyang  Y*,  Zhang  J,  Yang  H,  Wang  S     (2004)  Genome-wide  analysis  of 

     defense-responsive genes in bacterial blight resistance of rice mediated by the recessive R 

     gene xa13. Mol Genet Genomics 271: 111-120 
﻿                             CURRICULUM VITAE 

Personal Information 

    Name       Donghai PENG             Gender 

         Position Title                            professor 

     Working Department 

    Email                     donghaipeng@mail.hzau.edu.cn. 

                      State Key Laboratory of Agricultural Microbiology, 

                            College of Life Science and Technology, 
   Address 
                                                                                       Photo 
                               Huazhong Agricultural University, 

                           Wuhan, Hubei, People’s Republic of China 
     Tel                 + 86-27-87283455                  Fax             + 86-27-87280670 

Research Interest 

Research Areas 

     Discovery and utilization of new insecticidal protein gene resources. 

     Phage therapy in agriculture production. 

Research Proj ects 

     1.Novel insecticidal toxins and virulence factors in Bacillus thuringiensis 

     2.One of the important research directions in our lab is based upon the 

bacterium B. thuringiensis and its toxins. We are interesting in discovering, function 

and mechanism research of novel insecticide crystal proteins (Cry) and other virulence 

factors (such as Bel 1, Bmp 1, ColB, et al) during the infection process of B. thuringiensis in 

insects and nematode models. 

     3.Host-pathogen interactions between B. thuringiensis and its nematode target. 

     We are also interested in the both the mechanism of action of the B. thuringiensis cell and its 

toxins or virulence factors in the response of the insect or nematode host to intoxication. We also 

use this bacterium and its nematode host as a model system for studying a variety of ecological, 
﻿physiological, biochemical and genetic processes, especially in the innate immune signaling 

pathways in nematode host in the response to B. thuringiensis cell or its toxins. 

     4.Phage therapy for soil-borne bacterial diseases in agriculture production. 

     The increasing antibiotic resistances of bacteria makes phage therapy become an alternative 
strategy to replace antibiotics for bacterial disease treatment. Phage therapy has been used in the 

field of medicine and food industries have been a success, and there are a number of phage 

drugs undergoing clinical trials. We are interesting in development phage pesticides to prevent the 

most serious soil-borne bacterial diseases in agricultural production, such as soft rot or leaf wilt 

disease in vegetables. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education 

      2006/09—2009/06，Ph.D. of Microbiology College of Life Science and Technology, 

 Huazhong Agricultural University, Wuhan, China (Advisor: Professor Ming Sun) 

      2004/09—2006/06，Master of Biochemistry and Molecular Biology, College of Life 

 Science and Technology, Huazhong Agricultural University, Wuhan, China (Advisor: Professor 

 Ming Sun) 

      2000/09—2004/06, BA in Biotechnology, College of Life Science and Technology, 

 Huazhong Agricultural University, Wuhan, China 

 Experience 
﻿     2018/ 11—to date, Professor in College of Life Science and Technology, Huazhong 

Agricultural University, Wuhan, China 

     2017/06—2017/ 12, Visiting fellow in Department of 

Microbiology, University of Cornel, Ithaca, NY, USA (Working in Bs Lab with John D. 

Helmann, PhD) 

     2013/01—2018/ 10, Assistant professor in College of Life Science and Technology, 

Huazhong Agricultural University, Wuhan, China 

     2009/ 12—2010/02, Visiting fellow in School of Life 

Sciences, University of Sussex, Brighton, UK (Working in Bt Lab with Neil Crickmore, PhD) 

     2009/07—2012/ 12, Lecturer in College of Life Science and Technology, Huazhong 

Agricultural University, Wuhan, China 

Publications 

1.  Ju S, Chen H, Wang S, Lin J, Ma Y, Aroian RV, Peng D*, Sun M*. C. elegans monitor 

    energy status via the AMPK pathway to trigger innate immune responses against bacterial 

    pathogens. Commun Biol. 2022, 5(1):643. (Co-corresponding author) 

2.  Zheng Z, Zhang Y, Liu Z, Dong Z, Xie C, Bravo A, Soberón M, Mahillon J, Sun M*, Peng 

    D*. The CRISPR-Cas systems were selectively inactivated during evolution of Bacillus 

    cereus group for adaptation to diverse environments. ISME J, 2020, 14(6):1479-14933. 

3.  Shi JW, Peng D*, Zhang FJ, Ruan LF, Sun M*. The Caenorhabditis elegans 

    CUB-like-domain containing protein RBT-1 functions as a receptor for Bacillus 

    thuringiensis Cry6Aa toxin. PLoS Pathog, 2020, 16(5): e1008501. (Co-corresponding 

    author) 

4.  Wan L, Lin J, Du H, Zhang Y, Bravo A, Soberón M, Sun M, Peng D*. Bacillus 

    thuringiensis targets the host intestinal epithelial junctions for successful infection 

    of Caenorhabditis elegans. Environ Microbiol, 2019, 2 1(3):1086-1098. (Cover story) 

5.  Peng D, Luo X, Zhang N, Guo S, Zheng J, Chen L, Sun M*. Small RNA-mediated Cry toxin 
﻿    silencing allows Bacillus thuringiensis to evade Caenorhabditis elegans avoidance 

    behavioral defenses. Nucleic Acids Res, 2018, 46(1):159-173. 

6.  Dong Z, Xing S, Liu J, Tang X, Ruan L, Sun M, Tong Y, Peng D*. Isolation and 

    characterization of a novel phage Xoo-sp2 that infects Xanthomonas oryzae pv. oryzae. J 

    Gen Virol. 2018, 99(10):1453-1462. 

7.  Peng D, Wan D, Cheng C, Ye X, Sun M*. Nematode-specific cadherin CDH-8 acts as a 

    receptor for Cry5B toxin in Caenorhabditis elegans. Appl Microbiol Biotechnol. 2018, 

    102(8):3663-3673. 

8.  Peng D, Lin J, Huang Q, Zheng W, Liu G, Zheng J, Zhu L, Sun M*. A novel 

    metalloproteinase virulence factor is involved in B. thuringiensis pathogenesis in nematodes 

    and insects. Environ Microbiol, 2016, 8(3):846-862. 

9.  Peng D, Wang F, Li N, Zhang Z, Song R. Zhu Z, Ruan L, Sun M*. Single cysteine 

    substitution in Bacillus thuringiensis Cry7Ba 1 improves the crystal solubility and produces 

    toxicity to Plutella xylostella larvae. Environ Microbiol, 2011, 13:2820-2831. 

10. Peng D, Chai L, Wang F, Zhang F, Ruan L, Sun M*. Synergistic activity between Bacillus 

    thuringiensis Cry6Aa and Cry55Aa toxins against Meloidogyne incognita. Microb 

    Biotechnol, 2011, 4(6):794-798. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name         Nan PENG              Gender 

         Position Title                           Professor 

     Working Department 

    Email                         nanp@mail.hzau.edu.cn 

  Address 
                                                                                      Photo 
     Tel                  027-87281267                    Fax 

Research Interest 

     Mainly  engaged  in  beneficial  microorganism  screening,  engineering  and  applications. The 
     main  research  directions include: (1)  studying the mechanism  of  CRISPR-Cas  system;  (2) 
     screening,  engineering  and  functional  characterization of  beneficial microorganisms;  (3) 
     studying the production technologies for beneficial microorganisms. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      2000.09-2004.06, Huazhong Agricultural University, Bachelor of Bioengineering 

      2004.09-2009.12, Huazhong Agricultural University, Ph. D 

      2008.02-2009.11, University of Copenhagen, Visiting Ph. D student 

 Professional Experience: 

      2010.06-2012.12,    College  of  Life  Science   and  Technology,   Huazhong    Agricultural 
﻿University, Lecturer 

     2013.01-2017.12:     College   of Life   Science  and   Technology,    Huazhong    Agricultural 

University, Associate Professor 

     2017.01   to  now:   College   of  Life  Science   and  Technology,    Huazhong    Agricultural 

University, Doctoral supervisor 

     2017.04 to now: PI of State Key Laboratory of Agricultural Microbiology 

     2018.01   to  now:   College   of  Life  Science   and  Technology,    Huazhong    Agricultural 

University, Professor 

Publications 

1.      Li  Y*, Peng N*. (2019)  Endogenous  CRISPR-Cas  system-based  genome  editing  and 

     antimicrobials: review and prospects, Front Microbiol, 25;10:2471. 

2.     Zhang ZF, Pan  S, Liu  T, Li Y  and Peng N*. (2019) Cas4 nucleases can  effect  specific 

     integration of CRISPR spacers. J Bacteriol, 201, e00747-00718. 

3.     Liu  T, Liu Z, Ye Q, Pan  S, Wang, X, Li Y, Peng W, Liang Y, She Q, Peng N* (2017) 

     Coupling  transcriptional  activation  of CRISPR–Cas      system   and  DNA    repair genes  by 

     Csa3a in Sulfolobus islandicus. Nucleic Acids Res. 45(15): 8978-8992. 

4.       Peng N,  Han  W,  Li  Y,  Liang  Y,  She  Q.  (2017)  Genetic  technologies  for  extremely 

     thermophilic organisms of Sulfolobus genus, the only genetically tractable crenarchaea. Sci 

     China Life Sci. 60: 1-16. 

5.     Ren X, Wang J, Yu H, Peng C, Hu J, Ruan Z, Zhao S, Liang YX and Peng N*. (2016) 

     Anaerobic  and  sequential  aerobic production  of high-titer  ethanol  and  single  cell protein 

     from  NaOH-pretreated     corn   stover  by  a  genome    shuffling-modified    Saccharomyces 

     cerevisiae strain. Bioresource Technol. 2 18: 623-630. 

6.   Hu J, Lin Y, Zhang Z, Xiang T, Mei Y, Zhao S, Liang YX and Peng N*. (2016) High-titer 

     lactic acid production by Lactobacillus pentosus FL042 1 from corn stover using fed-batch 

     simultaneous saccharification and fermentation. Bioresource Technol. 2 14: 74-80. 
﻿7.      Li  Y, Pan  S, Zhang  Y, Ren  M, Feng  M, Peng N,  Chen  L,  Liang  Y,  She  Q* (2016) 

    Harnessing Type I and Type III  CRISPR-Cas systems for  genome editing, Nucleic Acids 

    Res. 29;44(4):e34. 

8.    Liu T, Li Y, Wang X, Ye Q, Li H, Liang XY, She Q and Peng N* (2015) Transcriptional 

    regulator-mediated   activation  of  adaptation  genes   triggers CRISPR     de  novo  spacer 

    acquisition. Nucleic Acids Res. 43 (2): 1044-1055. 

9.   Hu J, Zhang Z, Lin Y, Zhao S, Mei Y, Liang Y and Peng N*. (2015) High-titer lactic acid 

    production   from   NaOH-pretreated    corn  stover  by   Bacillus  coagulans  LA204    using 

    fed-batch     simultaneous     saccharification   and    fermentation     under    non-sterile 

    condition. Bioresource Technol. 182: 251-257. 

10.      Ao   X,  Li  Y,  Wang   F,  Feng   M,   Lin  Y,  Zhao   S, Liang   YX*    and  Peng   N* 

    (2013)  Sulfolobus Initiator  Element  is An  Important  Contributor  to Promoter  Strength. J 

    Bacteriol, 195(22):52 16-5222. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name       Lifang RUAN             Gender                Woman 

         Position Title                          Professor 

     Working Department 

    Email                      ruanlifang@mail.hzau.edu.cn 

  Address 

     Tel                 86-27-87280670                  Fax 

Research Interest 

     Pathogenic  mechanism    of  Xanthomonas  oryzae  pv.  oryzae ：  including  the  pathogenic 
     mechanism    related regulation;  Interaction between   pathogen   and   host; evolution  and 
     epidemiology  of Xanthomonas  oryzae pv. oryzae 。Research  concerning  Blight  disease  of 
     tomato  and  tobacco ：Reveal  the pathogenic  mechanism  of  interaction  between  Ralstonia 
     solanacearum and host, and then construct Disease resistant cultivar by genetic modification. 
     Identification of the  microbiome   of  rhizosphere  of  various tomato   cultivars, and  then 
     construct synthesis community for biocontrol of Blight disease. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      1992.09  -  1999.07  ， Huazhong    Agricultural  university, College   of life Science  and 
     technology, Bachelor/Master of Science 

      1999.09 - 2002.07，Wuhan university ，College of life Science, Doctor of Science 
      Professional Experiences: 

     2002,9 - 2004,7        Huazhong Agricultural university, Postdoctoral Fellow 

     2004,7   - 2015,12       Huazhong  Agricultural    university, College  of life Science  and 
﻿    technology, Associate Professor 

    2016,1  -                 Huazhong  Agricultural   university, College   of life Science  and 
    technology, Professor 

    2003,7 - 2004,2     Hong Kong Polytechnic University, research associate 

    2007,12 - 2009,6      University of Alberta, Postdoctoral Fellow 

Publications 

1.  Ruan, L. F., N. Crickmore, D. H. Peng and M. Sun (2015) "Are nematodes a missing link in 

    the  confounded    ecology  of  the  entomopathogen     Bacillus  thuringiensis?"  Trends   in 

    Microbiology 23(6): 34 1-346.   （Impact facter ：9.2 ） 

2.  Ruan,  L.,  N.  Crickmore  and  M.  Sun  (2015)  "Is  There Sufficient  Evidence  to  Consider 

    Bacillus  thuringiensis  a  Multihost  Pathogen?  Response  to  Loguercio  and  Argôlo-Filho." 

    Trends in Microbiology 23(10): 587.    （Impact facter ：9.2 ） 

3.  Ruan, L.*, H. Wang, G. Cai, D. Peng, H. Zhou, J. Zheng, L. Zhu, X. Wang, H. Yu, S. Li, C. 

    Geng and M. Sun (2015) "A two-domain protein triggers heat shock pathway and necrosis 

    pathway both in model plant and nematode." Environ Microbiol.       （Impact facter ：6.3） 

4.  Zheng D.H., Yao X.Y., Duan M., Luo Y.F., Liu  B., Qi P.Y., Sun M., Ruan L.F.* (2016). 

    “Two overlapping twocomponent systems in Xanthomonas oryzae pv. oryzae contribute to 

    full  fitness   in  rice   by   regulating   virulence   factors   expression”.    Sci.  Rep. 

     （doi:10.1038/srep22768 , Impact factor: 5.578） 

5.  Wang  J,  Guo  J, Wang  S, Zeng  Z, Zheng  D, Yao  X, Yu  H, Ruan  L*  (2017)  The  global 

    strategy  employed  by  Xanthomonas  oryzae  pv. oryzae  to  conquer  low-oxygen  tension. J 

    Proteomics 161: 68-77    （Impact facter  ：3.9 ） 

6.  Zheng  D,  Zeng  Z,  Xue  B,  Deng  Y,  Sun  M,  Tang  YJ,  Ruan  L.*  Bacillus  thuringiensis 

    produces the lipopeptide thumolycin to antagonize microbes and nematodes.Microbiol Res. 

    2018 (2 15):22-28. 

7.  Zheng   D,  Xue   B,  Shao  Y,  Yu   H,  Yao   X,  Ruan   L.*  Activation  of  PhoBR    under 

    phosphate-rich  conditions reduces the  virulence  of  Xanthomonas  oryzae  pv. oryzae. Mol 

    Plant Pathol. 2018(19):2066-2076. 
﻿8.  Liu, X. Y., L. F. Ruan, Z. F. Hu, D. H. Peng, S. Y. Cao, Z. N. Yu, Y. Liu, J. S. Zheng and 

    M.   Sun   (2010).  "Genome-wide      Screening   Reveals   the  Genetic   Determinants   of  an 

    Antibiotic Insecticide in Bacillus thuringiensis." Journal  of Biological  Chemistry  285(50): 

    39191-39200. 

9.  Ruan,  L.  F.,  A.  Pleitner,  M.  G.  Ganzle  and  L.  M.  McMullen  (2011).  "Solute  Transport 

    Proteins  and  the  Outer   Membrane     Protein  NmpC     Contribute   to Heat   Resistance   of 

    Escherichia coli AW 1.7." Applied and Environmental Microbiology 77(9): 2961-2967. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name         Ming SUN              Gender                  Man 

         Position Title                          Professor 

     Working Department 

    Email                       m98sun@mail.hzau.edu.cn 

  Address 

                                                                                     Photo 
     Tel                +86-27-87283455                  Fax 

Research Interest 

     Microbial pesticides 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education 

      1984.09-1988.07    Wuhan University, Microbiology BS 

      1988.09-1991.06    Huazhong Agricultural University, Microbiology MsD 

      1992.09-1995.12    Huazhong Agricultural University, Microbiology PhD 

 Working and Research Experiences 

      1991.07-now         Huazhong Agricultural University 

      1994. 05-1994.11    The Ohio State University, visiting scholar 
﻿     1997.06-1997.09       University of Waterloo, UNISCO-ASM visiting scholar 

     1997.10-1998.10       Institute of Molecular Agrobiology, visiting scholar 

     2002.07-2003.01       Cornell University, senior visiting scholar 

     2004.05-2004.11       The University of Hong Kong, Croucher visiting scholar 

Publications 

1.          Shi  J, Peng   D,  Zhang   F,  Ruan   L,  Sun  M   (2020)   The  Caenorhabditis    elegans 

     CUB-like-domain      containing   protein   RBT-1     functions   as  a  receptor   for  Bacillus 

     thuringiensis Cry6Aa toxin. PLoS Pathog. 16(5):e1008501. 

2.    Xin B, Liu H, Zheng J, Xie C, Gao Y, Dai D, Peng D, Ruan L, Chen H, Sun M (2020) In 

     Silico  analysis highlights the  diversity  and  novelty  of  circular  bacteriocins  in  sequenced 

     microbial genomes. mSystems. 5(3):e00047-20. 

3.    Zheng Z, Zhang Y, Liu Z, Dong Z, Xie C, Bravo A, Soberón M, Mahillon J, Sun M, Peng 

     D.  (2020)   The   CRISPR-Cas      systems   were   selectively  inactivated   during   evolution 

     of Bacillus cereus group for adaptation to diverse environments. ISME J. 14(6):1479-1493. 

4.   Deng Y, Chen H, Li C, Xu J, Qi Q, Xu Y, Zhu Y, Zheng J, Peng D, Ruan L, Sun M. (2019) 

     Endophyte  Bacillus  subtilis evade plant  defense by  producing  lantibiotic  subtilomycin  to 

     mask self-produced flagellin. Commun Biol, 2:368. 

5.    Saj id M, Geng C, Li M, Wang Y, Liu H, Zheng J, Peng D, Sun M. (2018) Whole-Genome 

     Analysis  of  Bacillus  thuringiensis  Revealing  Partial   Genes  as  a  Source  of  Novel   Cry 

     Toxins. Appl Environ Microbiol, 84(14). doi: 10.1128/AEM.00277-18. 

6.    Peng D, Luo X, Zhang N, Guo S, Zheng J, Chen L, Sun M. (2018) Small RNA-mediated 

     Cry   toxin  silencing   allows  Bacillus   thuringiensis   to  evade   Caenorhabditis    elegans 

     avoidance behavioral defenses. Nucleic Acids Res, 46(1):159-173. 

7.    Geng C, Liu Y, Li M, Tang Z, Muhammad S, Zheng J, Wan D, Peng D, Ruan L, Sun M. 

     (2018)  Dissimilar   Crystal  Proteins  Cry5Ca 1  and   Cry5Da1  Synergistically     Act  against 

     Meloidogyne    incognita   and  Delay   Cry5Ba-Based  Nematode       Resistance.  Appl   Environ 

     Microbiol, 83(18). doi: 10.1128/AEM.03505-16. 
﻿8.     Zheng J, Gao Q, Liu L, Liu H, Wang Y, Peng D, Ruan L, Raymond B, Sun M. (2018) 

    Comparative Genomics of Bacillus thuringiensis Reveals a Path to Specialized Exploitation 

    of Multiple Invertebrate Hosts. mBio, 8(4). doi: 10.1128/mBio.00822-17. 

9.   Du C, Cao S, Shi X, Nie X, Zheng J, Deng Y, Ruan L, Peng D, Sun M. (2017) Genetic and 

    biochemical  characterization  of a gene operon  for trans-aconitic  acid, a novel nematicide 

    from Bacillus thuringiensis. J Biol Chem, 292(8):3517-3530. 

10.    Zheng  J,  Peng  D,  Chen   L,  Liu H,  Chen   F,  Xu M,  Ju  S,  Ruan  L,  Sun  M.  (2016) 

    The  Ditylenchus   destructor  genome  provides  new    insights  into  the evolution of  plant 

    parasitic nematodes. Proc Biol Sci, 283(1835). pii: 20160942. 

11.  Zhang F, Peng D, Cheng C, Zhou W, Ju S, Wan D, Yu Z, Shi J, Deng Y, Wang F, Ye X, 

    Hu   Z,  Lin J,  Ruan  L,  Sun  M.   (2016)  Bacillus  thuringiensis Crystal  Protein  Cry6Aa 

    Triggers   Caenorhabditis   elegans   Necrosis   Pathway    Mediated   by   Aspartic  Protease 

    (ASP-1). PLoS Pathog, 12(1):e1005389. 

12.   Peng DH, Lin J, Huang Q, Zheng W, Liu  GQ, Zheng J, Zhu  L, Sun M, (2016) A novel 

    metalloproteinase    virulence  factor  is  involved  in  B.   thuringiensis  pathogenesis   in 

    nematodes and insects. Environ Microbiol, 18(3):846-862. 

13.  Ju S, Lin J, Zheng J, Wang S, Zhou H, Sun M. (2016) Alcaligenes faecalis ZD02, a novel 

    nematicidal bacterium with an extracellular serine protease virulence factor. Appl Environ 

    Microbiol, 82(7):2 112-2 120. 

14.    Ruan  L,  Crickmore  N,  Peng  D,  Sun  M.  (2015)  Are  nematodes  a  missing  link  in  the 

    confounded    ecology  of  the  entomopathogen    Bacillus  thuringiensis?  Trends  Microbiol, 

    23(6):34 1-346. 

15.  Ruan L, Wang H, Cai G, Peng D, Zhou H, Zheng J, Zhu L, Wang X, Yu H, Li  S, Geng 

    C, Sun M. (2015) A two domain protein triggers heat shock pathway and necrosis pathway 

    both in model plant and nematode. Environ Microbiol, 17(11):4547-4565. 

16.  Xin B, Zheng J, Xu Z, Li C, Ruan L, Peng D, Sun M (2015) Three novel lantibiotics ticin 

    A 1,   A3,   and   A4    have   extremely    stable  properties   and   are  promising    food 

    bio-preservatives. Appl Environ Microbiol, 81(20):6964-7220. 

17.  Xin B, Zheng J, Xu Z, Song X, Ruan L, Peng D, Sun M. (2015) The Bacillus cereus group 

    is   an   excellent   reservoir   of  novel    Lanthipeptides.   Appl    Environ    Microbiol, 
﻿     81(5):1765-1774. 

18.    Zheng  J,  Gänzle  MG,  Lin  XB,  Ruan  L,  Sun  M.  (2015)  Diversity     and  dynamics  of 

    bacteriocins from human microbiome. Environ Microbiol, 17(6):2 133-2 143. 

19.   Deng Y, Li CZ, Zhu YG, Wang PX, Qi QD, Fu JJ, Peng DH, Ruan LF, Sun M. (2014) 

    ApnI,  a  transmembrane  protein  responsible  for  subtilomycin  immunity,  unveils  a  novel 

    model for lantibiotic immunity. Appl Environ Microbiol, 80(20):6303-6315. 

20.  Luo X, Chen L, Huang Q, Zheng J, Zhou W ，Peng D ，Ruan L, Sun M. (2013) Bacillus 

     thuringiensis  metalloproteinase  Bmp 1  functions  as  a  nematicidal  virulence  factor.  Appl 

     Environ Microbiol, 79(2):460-468. 

2 1. Wang P, Liu Y, Zhang C, Zhu Y, Deng Y ，Guo S ，Peng D, Ruan L, Sun M. (2013)The 

    resolution and regeneration of a cointegrate plasmid reveals a model for plasmid evolution 

    mediated     by   conjugation    and    oriT   site-specific  recombination.     Environmental 

     Microbiology, 15(12):3305-3318. 

22.  Zheng J, Peng D, Song X , Ruan L, Mahillon J ，Sun M. (2013) Differentiation of Bacillus 

     thuringiensis, B. cereus,  and B. thuringiensis  on  the basis  of the  csaB  gene reflects host 

     source. Appl Environ Microbiol, 79(12):3860-3863. 

23.  Wang F, Liu Y, Zhang F, Chai L, Ruan L, Peng D, Sun M. (2012) Improvement of crystal 

     solubility and increasing toxicity against Caenorhabditis elegans by Asparagine substitution 

     in Block  3  of  Bacillus  thuringiensis  crystal  protein Cry5Ba.  Appl  Environ   Microbiol, 

     78(20):7197-7204. 

24.    Ye  W,  Zhu  L,  Liu  Y,  Crickmore  N,  Peng  D,  Ruan  L,  Sun  M.  (2012)  Mining  new 

     crystalprotein  genes  from  Bacillus thuringiensis  on  the  basis  of  mixed  plasmid-enriched 

     genome     sequencing    and    a  computational     pipeline.   Appl    Environ    Microbiol, 

     78(14):4795-4801. 

25.    Luo  Y,  Ruan  L,  Zhao  C,  Wang  C,  Peng  D,  Sun  M.  (2011)  Validation  of  the  intact 

     Zwittermicin  A  biosynthetic  gene  cluster and  discovery  of  a  complementary  resistance 

    mechanism in Bacillus thuringiensis. Antimicrob Agents Chemother, 55(9):4 161-4 169. 

26.  Peng D, Qiu D, Ruan L, Zhou C, Sun M. (2011) Protein elicitor PemG1 from Magnaporthe 

     grisea induces   SAR    in plants  through   the  salicylic acid  and   Ca2+-related signaling 

    pathways. Mol Plant Microbe Interact, 24(10):1239-1246. 
﻿27.  Peng D, Wang F, Li N, Zhang Z, Song R. Zhu Z, Ruan L, Sun M. (2011) Single cysteine 

    substitution in Bacillus thuringiensis Cry7Ba1 improves the crystal solubility and produces 

    toxicity to Plutella xylostella larvae. Environ Microbiol, 13(10):2820-2831. 

28.  Liu X, Ruan L, Hu Z, Peng D, Cao S, Zheng J, Liu Y, Yu Z, Sun M. (2010) Genome wide 

    screening   revealed  the  genetic  determinants   of a  antibiotic insecticide  in  Bacillus 

    thuringiensis. J Biol Chem, 285: 39191-39200. 

29.   Fang  S,  Wang  L,  Guo  W,  Zhang  X,  Peng  D,  Luo  C, Yu  Z,  Sun  M.  (2009)  Bacillus 

    thuringiensis  Bel  protein  synergizes  the  toxicity of  Cry 1Ac  protein  to  Helicoverpa 

    armigera   larvae  by  degrading  insect  intestinal mucin.  Appl   Environ  Microbiol,   75: 

    5237–5243. 

30.  Guo S, Liu M, Peng D, Ji S, Wang P,Yu Z, Sun M. (2008) New strategy for isolating novel 

    nematicidal   crystal protein genes  from   Bacillus thuringiensis  strain YBT-1518.    Appl 

    Environ Microbiol, 74: 6997-7001. 

31.  Sun M, Gene Engineering (2nd  edition), 2013, Beij ing: Higher Education Press. 
﻿                              CURRICULUM VITAE 

Personal Information 

    Name           Shuke Wu               Gender                    Male 

          Position Title                    Professor in Biotechnology 

     Working Department              College of Life Sciences & Technology 

    Email                         shukewu@mail.hzau.edu.cn 

   Address            No.1, Shizishan Rd., Wuhan 430070, P. R. China 

      Tel                                                     Fax 

Research Interest 

Biocatalysis, Enzyme Engineering, Synthetic Biology, Industrial Biotechnology 
1) Discover of novel enzymes and new pathways in microbes. 
2) Directed evolution and engineering of important enzymes in biological systems. 
3) Engineering of (chemo)-microbial cells factory for green agrochemical & pharmaceutical 
synthesis. 

Professional Memberships 

Guest Editor for Journals: Bioresources and Biop rocessing, Frontiers in Catalysis 
Reviewing for Journals: A CS Catalysis, A CS Sy nthetic Biology , A CS Chemical Biology , A CS Sustainable 
Chemistry  & Engineering, Angewandte  Chemie International Edition,  Chemical Review,  ChemSusChem, 
ChemCatChem, Journal of  Agricultural and Food Chemistry, Chemical Engineering Science, Biochemical 
Engineering Journal, Bioresources and Biop rocessing, Frontiers in Bioengineering and Biotechnology, etc. 

Other Roles 

 Awards: 
 Alexander von Humboldt Fellowship for Postdoctoral Researchers (2018-2020) 
 Seal of Excellence in Marie Skłodowska-Curie Actions (H2020-MSCA-IF-2017) 
 Swiss Government Excellence Scholarship (2017-2018, for postdoc study) 
 Singapore-MIT Alliance Fellowship (2010–2014, for PhD study) 

 Education & Working Experience 

 Working Experience: 
 2020.12–current:     Full   Professor,   College   of   Life  Sciences    &   Technology,     Huazhong 
 Agricultural University, China 
 2018.09–2020.11:  Humboldt        Postdoc   Fellow   with  Prof.  Uwe    T.  Bornscheuer,   Institute  of 
 Biochemistry, University of Greifswald, Germany. 
 2017.07–2018.08: Postdoc with Prof. Thomas R. Ward, Department of Chemistry, University of 
 Basel (UniBasel), Switzerland. 
 2016.01–2017.06: Research  Fellow  (Postdoc)  with  Prof. Zhi  Li, NUS  Synthetic  Biology  for 
 Clinical  and  Technological  Innovation     (SynCTI),  National  University     of  Singapore   (NUS), 
 Singapore. 
﻿Education: 
2010.07–2015.11:        Ph.D.    in   Chemical     and    Pharmaceutical       Engineering,     Singapore-MIT 
Alliance, National University of Singapore. Advisors: Prof. Zhi Li (NUS) and Prof. Daniel I. C. 
Wang (MIT). 
2013.03-2013.08: Visiting Ph.D. student, Chemical Engineering, MIT, USA. 
2006.09–2010.07: B.S. in Biotechnology (honors), Yuanpei College, Peking University, China. 

Publications 

Selected    First/Corresponding-Author  Publications:  (#:  equal               contribution;   *:  corresponding 
author) 

                 #                # 
1.   Shuke Wu, * Chao Xiang,        Yi Zhou, Mohammad  Saiful Hasan  Khan, Weidong  Liu, Christian  G. 
    Feiler, Ren Wei, Gert Weber, Matthias Höhne, Uwe T. Bornscheuer*. A growth selection system for 
    the directed evolution of amine-forming or converting enzymes. Nature Communications 2022, 13, 
     7458. [IF 17.694] DOI: 10.1038/s4 1467-022-35228-y 

2.   Shuke Wu, Radka Snaj drova, Jeffrey C. Moore, Kai Baldenius,* Uwe T. Bornscheuer*. Biocatalysis: 
    Enzymatic Synthesis for Industrial Applications. Angewandte Chemie International Edition 2021, 60 
     (1), 88-119. [IF 15.336] DOI: 10.1002/anie.202006648 
        ESI highly cited paper. 

3.   Shuke  Wu,* Yi  Zhou,  Daniel  Gerngross,  Markus  Jeschek,  Thomas  R. Ward*.  Chemo-enzymatic 
     Cascades to Produce  Cycloalkenes from  Bio-based Resources. Nature  Communications  2019,  10, 
     5060. [IF 14.919] DOI: 10.1038/s4 1467-019-13071-y 

4.   Shuke Wu,#  Yi Zhou,#  Johannes G. Rebelein,#  Miriam Kuhn, Hendrik Mallin, Jingming Zhao, Nico 

    V. Igareta, Thomas R. Ward*. Breaking Symmetry: Engineering Single-Chain Dimeric Streptavidin 
     as Host  for Artificial Metalloenzymes. Journal of      the American  Chemical Society  2019, 141 (40), 
     15869-15878. [IF 15.4 19] DOI: 10.102 1/j acs.9b06923 

5.   Shuke Wu, Yi Zhou, Tianwen Wang, Heng-Phon Too, Daniel I. C. Wang, Zhi Li*. Highly Regio- and 
    Enantioselective    Multiple   Oxy-   and  Amino-functionalizations      of  Alkenes  by   Modular    Cascade 
    Biocatalysis. Nature Communications 2016, 7, 11917. [IF 14.919] DOI: 10.1038/ncomms11917 

International Patents: 

1.  Zhi Li, Shuke Wu, Yi Zhou, Benedict Ryan Lukito. “Bioproduction of Phenethyl Alcohol, Aldehyde, 
    Acid, Amine, and Related Compounds.” WO20182 17168. 

2.  Zhi Li, Shuke Wu. “Production of Chiral 1,2-Amino Alcohols and α-Amino Acids from Alkenes by 
     Cascade Biocatalysis.” US20170067084. 

3.  Zhi  Li,  Shuke  Wu.  “Production      of  Enantiopure  α-Hydroxy     Carboxylic  Acids  from  Alkenes  by 
     Cascade Biocatalysis.” WO2014 189469. 
﻿Additional Information 

Website (English): https://faculty.hzau.edu.cn/shukewu/en/index 
ResearchGate: https://www.researchgate.net/profile/Shuke_Wu 
ORCID: 0000-0003-0914-9277; 
https://scholar.google.com/citations?user=KDE8huoAAAAJ&hl=en 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name        Shutong XU             Gender                 female 

         Position Title                          Professor 

     Working Department            Collage of Life Science & Technology 

    Email                      xushutong@mail.hzau.edu.cn 

  Address 

     Tel                                                 Fax 

Research Interest 

     Structure and mechanism of action of enzymes 
     Biological nitrogen fixation 
     Extracellular signal sensing and transmission 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 2017-present.  Professor.  College  of Life  Science  and  Technology,   Huazhong  Agricultural 
 University 
 2013-2017. Postdoc. Dana-Farber Cancer Institute, Harvard Medical School 
 2007-2013.PhD. Institute of Biochemistry and Cell Biology, Shanghai Academy of Biosciences, 
 Chinese Academy of Sciences 
 2003-2007. B.A. College of Life Science and Technology, Huazhong University of Science and 
 technology 

 Publications 
﻿1.  Li X, Singh NK, Collins DR, Ng R, Zhang A, Lamothe-Molina PA, Shahinian P, Xu S, Tan 

K, Piechocka-Trocha A, Urbach JM, Weber JK, Gaiha GD, Takou Mbah OC, Huynh T, Cheever 

S, Chen J, Birnbaum M, Zhou  R, Walker BD, Wang JH. Molecular basis of differential HLA 

class  I-restricted  T  cell  recognition  of  a  highly  networked  HIV  peptide. Nat  Commun. 2023 

May 22;14(1):2929. 

2.  Zhu  L,  Wei  X,  Cong  J,  Zou  J,  Wan  L,  Xu S#.  Structural  insights  into  mechanism  and 

specificity of the plant protein O-fucosyltransferase SPINDLY. Nature Communications, 2022, 

13(1): 7424-7436 

3.  Tao W#, Lei H, Luo W, Huang Z, Ling P, Guo M, Wan L, Zhai K, Huang Q, Wu Q, Xu  S, 

Zeng  L, Wang X, Dong Z, Rich  J, Bao  S#. NIR  Drives  Glioblastoma  Growth  by  Promoting 

Ribosomal DNA Transcription in Glioma Stem Cells. Neuro-Oncology, 2022, XX(XX): 1-13. 

4.  Tao W#, Lei H, Luo W, Huang Z, Ling P, Guo M, Wan L, Zhai K, Huang Q, Wu Q, Xu  S, 

Zeng  L, Wang X, Dong Z, Rich  J, Bao  S#. NIR  Drives  Glioblastoma  Growth  by  Promoting 

Ribosomal DNA Transcription in Glioma Stem Cells. Neuro-Oncology, 2022, XX(XX): 1-13. 
﻿                             CURRICULUM VITAE 

Personal Information 

    Name       Shunping YAN            Gender 

         Position Title                           Professor 

     Working Department 

    Email                         spyan@mail.hzau.edu.cn 

  Address 

                                                                                      Photo 
     Tel                  027-59209179                    Fax 

Research Interest 

Plant disease resistance 

DNA damage repair in plants 

Hormone signal transduction 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

 2001-2006     Doctoral Degree, Institute of Plant Physiology and Ecology, Shanghai Institutes 

 for Biological Sciences, Chinese Academy of Sciences, China 

 1997-2001 Bachelor ’s Degree, College of Life and Environmental Sciences, Zhej iang Normal 

 University, China 
﻿Professional Experiences: 

2014-now Professor, College of Life Science and Technology, Huazhong Agricultural 

University, China 

2011- 2014    Research Scientist, Department of Biology, Duke University, USA 

2006 - 2011   Research Associate, Department of Biology, Duke University, USA 

Publications 

1.  Wang LL, Chen  HC, Wang CY, Hu ZJ, Yan  SP#.         Negative regulator  of E2F transcription 

    factors  links  cell cycle   checkpoint   and  DNA     damage    repair. PNAS,     2018,   115: 

    E3837–E3845 

2.  Yan SP, Dong XN. Perception of the plant immune signal salicylic acid. Current Opinion in 

    Plant Biology, 2014, 20:64-68. 

3.  Yan  SP,  Wang  W,  Marqués  J,  Mohan  R,  Saleh  A,  Durrant  WE,  Song  JQ,  Dong  XN. 

    Salicylic  acid  activates  DNA  damage  responses  to  potentiate  plant  immunity.  Molecular 

    Cell, 2013, 52: 602-610. 

4.  Fu ZQ*,Yan SP*, Saleh A*, Wang W, Ruble J, Oka N, Mohan R, Spoel S, Tada Y, Zheng 

    N, Dong XN. NPR3 and NPR4 are receptors for the immune signal salicylic acid in plants. 

    Nature, 2012, 486: 228-232. 

5.  Yan  SP,  Zhang  QY,  Tang  ZC,  Su  WA,  and  Sun  WN.  Comparative  proteomic  analysis 

    provides  new   insights  into  chilling  stress responses   in rice.  Molecular   &   Cellular 

    Proteomics, 2006, 5: 484-496. 

6.  Yan  SP,  Tang  ZC,  Su  WA,  and    Sun  WN.  Proteomic  analysis  of  salt stress-responsive 

    proteins in rice root. Proteomics, 2005, 5: 235-244. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name         Ping YIN              Gender 

         Position Title                          Professor 

     Working Department 

    Email                       yinping@mail.hzau.edu.cn 
                                                                                     Photo 

  Address 

     Tel                027-87288920 (O)                 Fax 

Research Interest 

1.   Structural study on RNA modification and metabolism; 

2.   Structure and biochemical investigation of plant organelle biogenesis; 

3.   Structure and function of membrane proteins. 

Professional Memberships 

     Outstanding Youth Science Foundation; 

     Chang Jiang Youth Scholar Program; 

     National Youth Talent Support Program. 

Other Roles 

 Education & Working Experience 

 Education: 

      Ph.D.   (2009)   Molecular Biology and Biochemistry 

                      National Key Laboratory of Virology, School of Life Sciences, 

                      Wuhan University, Wuhan, P. R. China. 

      M. S.   (2006)   Molecular Biology and Biochemistry 

                      National Key Laboratory of Virology, School of Life Sciences, 
﻿                         Wuhan University, Wuhan, P. R. China. 

      B. S.    (2003)     Biotechnology 

                         School of Life Sciences, Wuhan University, Wuhan, P. R. China. 

Professional Experiences: 

      2013.09-Present      Professor 

      School    of  Life  Sciences    and   Technology,      National   key   Laboratory     of  Crop    Genetic 

Improvement, 

      Huazhong Agricultural University, 

       Wuhan, P. R. China. 

      2009.07-2013.08 Postdoctoral Fellow 

       Center of Structural Biology, School of Life Sciences, 

       Tsinghua University, Beij ing, P. R. China. 

       Advisor: Dr Nieng Yan, Professor. 

      2008.10-2009.04       Visiting Student 

       Center of Structural Biology, School of Life Sciences, 

       Tsinghua University, Beij ing, P. R. China. 

       Advisor: Dr Nieng Yan, Professor. 

Publications 

            #         #                                                                        * 
1.    Yan J , Yao Y , Hong S, Yang Y, Shen C, Zhang Q, Zhang D, Zou T, Yin P .Delineation of 

     pentatricopeptide       repeat     codes      for    target    RNA       prediction.     Nucleic      Acids 

     Research. 2019 Apr 23; 47(7): 3728-3738. doi: 10.1093/nar/gkz075. 

                  #            #                                                        * 
2.     Wang Q , Zhang D , Guan Z, Li D, Pei K, Liu J, Zou T and Yin P . DapF stabilizes the 

     substrate-favoring     conformation      of  RppH     to  stimulate   its  RNA-pyrophosphohydrolase 

     activity in Escherichia coli. Nucleic Acids Research. 2018 May 28. 46(13): 6880-6892. doi: 

     10.1093/nar/gky528. 
﻿                 #                                                                          * 
3.        Liu  J , Guan Z, Liu  H, Qi L, Zhang D, Zou  T, and Yin P . Structural insights into the 

      substrate      recognition       mechanism          of   Arabidopsis        thaliana      GPP-bound         NUDX 1         for 

      noncanonical         monoterpene          biosynthesis.       Mol.     Plant.     2017      Oct    18;    11(1):2 18-22 1. 

      doi:10.1016/j .molp.2017.10.006. 

               #              #                                                                          * 
4.     Yan J , Zhang Q , Guan Z, Wang Q, Li L, Ruan F, Lin R, Zou T, Yin P . MORF9 increases 

      the  RNA-binding  activity  of  PLS-type  pentatricopeptide  repeat  protein  in  plastid  RNA 

      editing. Nature Plants. 2017 Apr 10; 3:17037. doi: 10.1038/nplants.2017.37. 

                    #          #                                                                                     * 
5.      Zhang D , Liu Y , Wang Q, Guan Z, Wang J, Liu J,&shy;&shy; Zou T, Yin P . Structural 

      basis      of    prokaryotic        NAD-RNA             decapping         by     NudC.       Cell      Research.        2016 

      Sep;26(9):1062-6. doi: 10.1038/cr.2016.98. Epub 2016 Aug 26. 

                   #           #           # 
6.      Wang X , Feng J , Xue Y , Guan Z, Zhang D, Liu Z, Gong Z, Wang Q, Huang J, Tang C, 

                         * 
      Zou  T, Yin P . Structural basis of N6-adenosine methylation by the METTL3-METTL 14 

      complex. Nature. 2016 May 25;534(7608):575-8. doi: 10.1038/nature18298 

                 #              #            # 
7.     Shen C , Zhang D , Guan Z , Liu Y, Yang Z, Yang Y, Wang X, Wang Q, Zhang Q, Fan S, 

                           * 
      Zou     T,  Yin    P .   Structural     basis    for   the   specific     single-stranded        RNA      recognition      by 

      designer         pentatricopeptide             repeat        protein.         Nat.       Commun.             2016        Apr 

      18;7:11285. doi:          10.1038/ncomms11285. 

                 #              #                                                             * 
8.     Shen C , Wang X , Liu Y, Li Q, Yang Z, Yan N, Zou T, Yin P . Specific RNA recognition 

      by    designer     pentatricopeptide         repeat     protein.     Mol     Plant.    2015     Apr;8(4):667-70.         doi: 

      10.1016/j .molp.2015.01.001 

               #        # 
9.     Yin P , Li Q , Yan C, Liu Y, Liu J, Yu F, Wang Z, Long J, He J, Wang H, Wang J, Zhu J, 

                         * 
      Shi Y, Yan N . Structural basis for the modular recognition of single-stranded RNA by PPR 

      proteins. Nature. 2013 Dec 5; 504 (7478): 168-171. doi: 10.1038/nature12651 

                  #              # 
10.      Yin  P ,  Deng  D ,  Yan  C,  Pan  X,  Xi  J,  Yan  N,  Shi  Y*.  Specific  DNA-RNA  hybrid 

      recognition        by    TAL       effectors.     Cell     Reports.      2012      Oct     25;    2    (4):707-13.       doi: 

      10.1016/j .celrep.2012.09.001. (The Best of Cell Reports in 2012) 

                  #          # 
11.    Deng D , Yin P , Yan C, Pan X, Gong X, Qi S, Xie T, Mahfouz M, Zhu Jian-Kang, Yan 
﻿     N*, Shi Y*. Recognition of methylated DNA by TAL effectors. Cell Research. 2012 Oct; 

     22 (10):1502-4. doi: 10.1038/cr.2012.127. 

                #         # 
12.    Hao Q , Yin P , Li W, Wang L, Yan  C, Lin  Z, Wu  JZ, Wang J, Yan  SF, Yan N*. The 

     molecular      basis    of   ABA-independent           inhibition     of   PP2Cs      by   a   subclass     of   PYL 

     proteins. Mol Cell. 2011 Jun 10;42(5):662-72. doi: 10.1016/j .molcel.2011.05.011. 

                #           #           #            # 
13.     Yin  P ,  Fan  H ,  Hao  Q ,  Yuan  X ,  Wu  D,  Pang  Y,  Yan  C,  Li  W,  Wang  J,  Yan  N*. 

     Structural  insights  into  the  mechanism  of  abscisic  acid  signaling  by  PYL  proteins. Nat 

     Struct    Mol    Biol.  2009  Dec;       16   (12):   1230-6.  doi:     10.1038/nsmb.1730.  (Cover            Paper) 

     (Breakthrough of the year in Science ) 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name       Meng YUAN               Gender                  Male 

         Position Title                          Professor 

     Working Department            Collage of Life Science & Technology 

    Email                        myuan@mail.hzau.edu.cn 

                 National Key Laboratory of Crop Genetic Improvement, 
  Address 
                            Huazhong Agricultural University 
     Tel                  027-87281812                   Fax 

Research Interest 

     Integrate the knowledge and technology of genetics, 
     biochemistry, molecular biology, bioinformatics and molecular plant pathology to carry out 
     research on the mining, function and regulation mechanism of rice disease resistance genes 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 2018-present.  Professor.  College  of Life  Science  and  Technology,   Huazhong  Agricultural 
 University 
 2013-2018.Associate    Professor.   College   of  Life  Science   and   Technology,    Huazhong 
 Agricultural University 
 2011-2012.   Lecturer.  College   of  Life  Science  and   Technology.   Huazhong    Agricultural 
 University 
 2003-2010. PhD. Biochemistry and Molecular Biology. Collage of Life Science & Technology. 
 Huazhong Agricultural University 
 1999-2003.   B.A.   Forestry. College   of Horticulture  and  Forestry.  Huazhong    Agricultural 
 University 

 Publications 
﻿1.  Cao J, Chu C, Zhang M, He L, Qin L, Li X, Yuan M (2020) Different cell wall-degradation 

ability  leads to  tissue-specificity  between  Xanthomonas  oryzae pv. oryzae  and  Xanthomonas 

oryzae pv. oryzicola. Pathogens. 9:187. 

2.  Ke Y, Yuan  M, Liu  H, Hui  S, Qin  X, Chen  J, Zhang  Q, Li X, Xiao J, Zhang  Q, Wang  S 

(2020)  The  versatile functions  of OsALDH2B 1  provide     a  genic  basis for growth-defense 

trade-offs in rice. Proc Natl Acad Sci USA. 117:3867-3873. 

3.  Yoo  H#,  Greene  GH#,  Yuan  M#,  Xu   G,  Burton  D,  Liu  L,  Marqués  J,  Dong  X (2020) 

Translational regulation of metabolic dynamics during effector-triggered immunity. Mol Plant. 

13:88-98. 

4.  Cao J, Zhang M, Zhu  M, He L, Xiao J, Li X, Yuan  M  (2020) Autophagy-like cell  death 

regulates hydrogen peroxide and calcium  ion  distribution in Xa3/Xa26-mediated resistance to 

Xanthomonas oryzae pv. oryzae. Int J Mol Sci. 2 1:194. 
﻿                             CURRICULUM VITAE 

Personal Information 

    Name      Jianwei ZHANG            Gender                   Man 

         Position Title                           Professor 

     Working Department 

    Email                         j zhang@mail.hzau.edu.cn 

                 National Key Laboratory of Crop Genetic Improvement 
   Address      #B 122, Huazhong Agricultural University,Wuhan 430070,                 Photo 
                                           China 
     Tel                 +86-27-87286166                   Fax 

Research Interest 

     Bioinformatics, Genomics 

Professional Memberships 

Other Roles 

 Education & Working Experience 

      2006.6: Doctor  of  Science  (Biochemistry  &  Molecular  Biology  with  a  specialization  in 
 Bioinformatics), Huazhong Agricultural University (HZAU) 
      2001.6: Bachelor of Science (Biotechnology), HZAU 

      Huazhong Agricultural University: National Key Laboratory of Crop Genetic Improvement 

           2019.11 – present: Professor 

           2013.5 – 2019.10: Adjunct Research Fellow 

      University of Arizona: School of Plant Sciences & Arizona Genomics Institute 

           2013.3 – 2019.5: Research Assistant Professor 
﻿          2010.11 – 2013.2: Assistant Research Scientist 

          2006.9 – 2010.10: Research Associat 

Publications 

1.  Song J-M, Lei Y, Shu C-C, Ding Y, Xing F, Liu H, Wang J, Xie W, Zhang J# and Chen L-L# 

    (#corresponding    authors).  Rice   Information   GateWay     (RIGW):    A   Comprehensive 

    Bioinformatics Platform  for  Indica Rice  Genomes. Molecular  Plant, 2018,  11(3):505-507. 

    DOI: 10.1016/j .molp.2017.10.003 

2.  Zhang J*, Chen L* (*co-first  authors), Sun  S, Kudrna D, Copetti D, Li W, Mu T, Jiao W, 

    Xing F, Lee S, Talag J, Song J, Du B, Xie W, Luo M, Maldonado C, Goicoechea J, Xiong L, 

    Wu C, Xing Y, Zhou D, Yu S, Zhao Y, Wang G, Yu Y, Luo Y, Hurtado B, Danowitz A, Wing 

    R  and  Zhang  Q. Building  two  indica  rice  reference  genomes with  PacBio  long  read  and 

    Illumina   paired-end    sequencing    data.   Scientific  Data,   2016,    3:160076.    DOI: 

    10.1038/sdata.2016.76 

3.  Zhang J*, Chen L*, Xing F* (*co-first authors), Kudrna D, Yao W, Copetti D, Mu T, Li W, 

    Song J, Xie W, Lee S, Talag J, Shao L, An Y, Zhang C, Ouyang Y, Sun S, Jiao W, Lv F, Du 

    B, Luo M, Maldonado C, Goicoechea J, Xiong L, Wu C, Xing Y, Zhou  D, Yu  S, Zhao Y, 

    Wang G, Yu Y, Luo Y, Zhou Z, Hurtado B, Danowitz A, Wing R and Zhang Q. Extensive 

    sequence   divergence  between   the  reference genomes   of  two  elite indica  rice varieties 

    Zhenshan  97  and  Minghui  63. Proceedings  of  the National Academy  of  Sciences  of  the 

    United States of America, 2016, 113(35):E5163-E5171. DOI: 10.1073/pnas.1611012 113 

4.  Zhang  J#, Kudrna  D, Mu  T, Li  W,  Copetti  D, Yu Y, Goicoechea  J,  Lei Y  and  Wing  R# 

    (#corresponding authors). Genome puzzle master (GPM): an integrated pipeline for building 

    and   editing  pseudomolecules     from    fragmented    sequences.   Bioinformatics,   2016, 

    32(20):3058-3064. DOI: 10.1093/bioinformatics/btw370 

5.  Wei F*, Zhang J* (*co-first  authors), Zhou  S, He R,  Schaeffer  M, Collura K, Kudrna D, 

    Faga B, Wissotski M, Golser W, Rock S, Graves T, Fulton R, Coe E, Schnable P, Schwartz 

    D, Ware D, Clifton  S, Wilson R and Wing R. The Physical and Genetic Framework of the 

    Maize      B73     Genome.       PLoS      Genetics,     2009,      5(11):e1000715.      DOI: 

    10.1371/j ournal.pgen.1000715 

6.  Zhang J, Li C, Wu C, Xiong L, Chen G, Zhang Q and Wang S. RMD: a rice mutant database 
﻿    for  functional  analysis  of  the  rice  genome. Nucleic Acids  Research,  2006,  34:D745-748. 

    DOI: 10.1093/nar/gkj 016 

7.  Zhang J, Feng  Q, Jin  C, Qiu D, Zhang L, Xie K, Yuan D, Han B, Zhang Q and Wang  S. 

    Features  of  the  expressed  sequences  revealed  by  a  large-scale  analysis  of  ESTs  from  a 

    normalized  cDNA library  of the  elite  indica rice  cultivar  Minghui  63. The Plant  Journal, 

    2005, 42:772-780. DOI: 10.1111/j .1365-313X.2005.02408. 

8.  Full list of publications (https://scholar.google.com/citations?user=LbvoiHoAAAAJ&hl=en) 
﻿                             CURRICULUM VITAE 

Personal Information 

Name          Zhang Jibin       Gender                 Male 

Position Title                  Professor 
                                College of Life Science and Technology, 
Working Department 
                                Huazhong Agricultural University 
Email          zhangjb@mail.hzau.edu.cn 

              No.1, Shizishan Street, Hongshan District, Wuhan, Hubei 
Address 
              Province · 430070 · P.R.China 

     Tel      86-27-87287701                                Fax     86-27-87287254 

Research Interest 

 (1)  Bio-conversion: Research on the mechanism, technology and application of organic 

      waste co-conversion by functional microbes and insect (such as black soldier fly). 

 (2)  Bio-pesticides：Discovery of new active substances produced by microorganisms and 

      insects, structure and function, mechanism of action, and application research. 

Professional Memberships 

2 associate professor, 1 lecturer 

Other Roles 

 Member, Chinese Academy for Microbiology, China 

 Member, The Entomological Society of China, China 

 Education & Working Experience 

 Education: 

    1982.09-1986.06, Hubei University, Bachelor of Science 

    1986.09-1989.06, Huazhong Agricultural University, Master of Science 

    2001.09-2006.06, Huazhong Agricultural University, Ph.D of Science 

 Working Experiences: 

    1989.7-2002.12, Institute of Parasitic Disease, Hubei Academy of Medical 

                      Sciences, Assistant Researcher / Associate Researcher 

    1994.4-1994.6, University of London ，Visiting Scholar 

   2002.12-2006.2, Institute of Parasitic Disease, Hubei Academy  of Medical  Sciences, 

                      Researcher 

   2010.8-2011.8,  USDA      Plant  Root  Disease  Biological   Control  Laboratory,  Visiting 

                      Scholar 

   2006.3-present,   State  Key   Laboratory   of Agricultural   Microbiology    and  National 

                      Engineering Research Center of Microbial Pesticides, College of Life 
﻿                     Science  and  Technology, Huazhong Agricultural University ，fixed 

                     member ，professor 

                     Microbial Product Quality Supervision and Testing Center (Wuhan), 

                     Ministry of Agriculture，Deputy Director 

Publications 

1.  Yu Y Q, Zhang J, Zhu F L, Fan M X, Zheng J S, Cai M M, Zheng L Y, Huang F, Yu Z N and 
    Zhang J B* Enhanced protein degradation by black soldier fly larvae (Hermetia illucens L.) 
    and its gut microbes. Frontier Microbiology, 2023,13:1095025. 
2.  Zhang Y P, Xiao X P, Elhag O, Cai M M, Zheng L Y, Huang F*, Jordan H R, Tomberlin J K; 
    Sze  S H; Yu  Z N; Zhang  J  B. Hermetia  illucens  L. larvae–associated  intestinal microbes 
    reduce the transmission risk of zoonotic pathogens in pig manure, Microbial Biotechnology, 
    2022, 15(10): 2631-2644. 
3.  Cheng  W  L,  Xue  H,  Yang  X,  Huang  D,  Cai  M       M,  Huang  F,  Zheng  LY,  Peng  D  H, 
    Thomashow  L  S, Weller  D  M, Yu Z N, Zhang J  B*. Multiple receptors contribute to the 
    attractive  response  of  Caenorhabditis  elegans  to  pathogenic  bacteria.2022,  Microbiology 
    Spectrum,10.1128. 
4.  Wanli   Cheng,   Xue  Yang,   Hua   Xue,  Dian   Huang,   Minmin    Cai,  Feng  Huang,    Longyu 
    Zheng, Ziniu Yu and Jibin Zhang*.Reproductive toxicity of furfural acetone in Meloidogy ne 
    incognita and Caenorhabditis elegans.2022,Cells, 11, 401. 
5.  Yang C R; Ma S T; Li F; Zheng LY; Tomberlin J K; Yu Z N; Zhang J B; Yu C;Fan M X*; 
    Cai M M*; Characteristics and mechanisms of ciprofloxacin  degradation by black  soldier 
    fly  larvae  combined    with  associated  intestinal  microorganisms,    Science   of  the  Total 
    Environment, 2022, 811(151371). 
6.  Wanli Cheng, Li Zeng, Xue Yang, Dian Huang, Hao Yu, Wen Chen, Minmin Cai, Longyu 
    Zheng,   Ziniu  Yu,  Jibin  Zhang*.   Preparation   and  efficacy  evaluation   of Paenibacillus 
    p oly myxa  KM2501-1 microbial  organic  fertilizer  against  root-knot  nematodes. Journal  of 
    Integrative Agriculture, 2022, 2 1(2): 542-551. 
7.  Osama  Elhag,  Yuanpu  Zhang,  Xiaopeng  Xiao,  Minmin  Cai,  Longyu  Zheng,  Heather  R. 
    Jordan,  Jeffery  K.  Tomberlin,   Feng   Huang,   Ziniu  Yu  and   Jibin Zhang*    Inhibition  of 
    zoonotic  pathogens  naturally  found  in  pig  manure  by  black   soldier  fly  larvae  and  their 
    intestine bacteria. Insects, 2022, 13, 66. 
8.  Wen  Chen, Jinping Wang, Dian  Huang, Wanli  Cheng, Zongze  Shao, Minmin  Cai,Longyu 
    Zheng, Ziniu Yu  and Jibin  Zhang* Volatile organic compounds from Bacillus  ary abhattai 
    MCCC 1K02966 with multiple modes against Meloidogyne incognita. Molecules, 2022, 27, 
    103. 
9.  Minmin Cai, Li Li, Zhengzheng Zhao, Ke Zhang, Fang Li, Chan Yu, Rongfang Yuan, Beihai 
    Zhou,  Zhuqing  Ren,  Ziniu  Yu    and  Jibin  Zhang*.  Morphometric  characteristic  of  black 
    soldier fly (Hermetia illucens) Wuhan strain and its egg production improved by selectively 
    inbreeding. Life, 2022, 12, 873. 
10. Jingj ing Zhang, Jiahui Li, Yuanzhi Peng, Xiaokun Gao, Qi Song, Hongyuan Zhang, Osama 
    Elhag,  Minmin    Cai,  Longyu   Zheng,  Ziniu  Yu,  Jibin  Zhang*.   Structural  and  functional 
    characterizations  and  heterogenous  expression  of  the  antimicrobial  peptides, Hidefensins, 
    from   black  soldier  fly, Hermetia    illucens  (L.). Protein   Expression   and   Purification, 
    2022,192,106032. 
﻿11. Cheng WL, Chen Z, Zeng L, Yang X, Huang D, Zhai YL, Cai MM, Zheng LY, Thomashow 
    LS, Weller DM, Yu ZN, Zhang JB. Control of Meloidogy ne incognita in three-dimensional 
    model systems and pot experiments by the attract-and-kill effect  of furfural acetone. Plant 
    Disease, 202 1, 105:2 169-2 176. 
12. Zhang J B, Yu Y Q, Tomberlin J K, Cai M M, Zheng L Y, Yu Z N. Organic side streams: 
    Using  microbes  to  make  substrates  more  fit  for  mass  producing  insects  for  use  as  feed. 
    Journal of Insects as Food and Feed, 202 1; 7(5): 597-604. 
13. Zhang J B, Zhang J, Li J H, Tomberlin J K, Xiao X P, ur Rehman K, Cai M M, Zheng L Y, 
    Yu  Z  N.  Black  soldier  fly: A  new  vista  for  livestock  and  poultry  manure  management. 
    Journal of Integrative Agriculture, 202 1, 20(5): 1167-1179. 
14. Mingying    Shao,   Zhixin   Wang,   Yingzhi   He,  Zhen    Tan,  Jibin  Zhang.   Fecal  Microbial 
    Composition and Functional Diversity of Wuzhishan Pigs at Different Growth Stages. AMB 
    Express, 202 1, 11(88):1-9. 
15. Fan, Mingxia; Liu, Nian; Wu, Xiangj i; Zhang, Jibin; Cai, Minmin*. Tolerance and removal 
     of four polycyclic aromatic hydrocarbon compounds (PAHs) by black soldier fly (Diptera: 
     Stratiomyidae), Environmental Entomology, 2020, 49(3): 667-672. 
16. A.A. Soomro, M. Cai, Z.A. Laghari, L. Zheng, K. ur Rehman, X. Xiao, S. Hu, Z.Yu and J. 
     Zhang*.  Impact    of  heat  treatment  on  microbiota  of  black   soldier fly  larvae  reared  on 
     soybean curd residues. Journal of Insects as Food and Feed, 202 1, 7(3): 329-343. 
17. Cheng WL, Yang X, Zeng L, Huang D, Cai MM, Zheng LY, Yu ZN, Zhang JB*. Evaluation 
     of  Multiple  Impacts  of Furfural Acetone  on  Nematodes  In  Vitro  and  Control  Efficiency 
     against Root-Knot Nematodes in Pots and Fields. Antibiotics-Basel. 2020, 9: 605. 
18. Yaqing Huang, Yongqiang Yu, Shuai Zhan, Jeffery K. Tomberlin, Dian Huang, Minmin Cai, 
     Longyu Zheng, Ziniu Yu, Jibin Zhang*.. Dual oxidase Duox and Toll-like receptor 3 TLR3 
     in the Toll pathway suppress zoonotic pathogens through regulating the intestinal bacterial 
     community homeostasis in Hermetia illucens L. PLoS ONE. 2020, 15(4): e0225873. 
19. Jibin Zhang*, Dmitri V. Mavrodi, Mingming Yang, Linda S. Thomashow, Olga V. Mavrodi, 
     Jason   Kelton,  and  David  M.  Weller*.  Pseudomonas       sy nxantha  2-79  transformed  with 
     pyrrolnitrin   biosynthesis   genes   has   improved    biocontrol   activity  against   soilborne 
     pathogens of wheat and canola. Phytopathology, 2020, 110:1010-1017. 
20. Wu Li, Qing Li, YuanYuan Wang, Longyu Zheng, Yanlin Zhang, Ziniu Yu, Huanchun Chen, 
     Jibin  Zhang*  Efficient  bioconversion     of  organic  wastes  to  value-  added  chemicals  by 
     soaking, black  soldier  fly  (Hermetia  illucens  L.)  and  anaerobic  fermentation. Journal  of 
     Environmental Management. 2018, 227:267-276. 
2 1. Zhang    JB*,  Tomberlin    JK,   Cai  MM,    Xiao   XP,   Zheng   LY,   Yu  ZN.   Research    and 
     industrialization  of Hermetia  illucens  L.  in  China. Journal  of  Insects  as  food  and  feed. 
     2020,6(1):5-12. 
22. Dian Huang , Chen Yu, Zongze Shao, Minmin Cai, Guangyu Li , Longyu Zheng, Ziniu Yu 
     and  Jibin  Zhang*.  Identifification   and  characterization   of  nematicidal  volatile  organic 
     compounds  from  deep-sea  Virgibacillus  dokdonensis  MCCC  1A00493. Molecules  2020, 
     25(744):1-14. 
23. Mazza  L,  Xiao  X, Ur  Rehman  K,  Cai  M, Zhang  D,  Fasulo  S,  Tomberlin  JK, Zheng  L, 
     Soomro AA,  Yu  Z,  Zhang  J*.  Management  of  chicken  manure  using  black  soldier  fly 
     (Diptera: Stratiomyidae) larvae assisted by companion bacteria.Waste Management. 2020, 
      102: 312-318. 
24. Huang Dian, Yu  Chen, Shao Zongze, Cai Minmin, Li Guangyu, Zheng Longyu, Yu Ziniu 
﻿     and  Zhang    Jibin*.  Identifification and  characterization   of  nematicidal  volatile  organic 
     compounds  from  deep-sea  Virgibacillus  dokdonensis  MCCC  1A00493. Molecules  2020, 
     25(744):1-14. 
25.  Zhang    JB*,  Tomberlin    JK,   Cai  MM,    Xiao   XP,   Zheng   LY,   Yu  ZN.   Research    and 
     industrialization  of Hermetia  illucens  L.  in  China. Journal  of  Insects  as  food  and  feed. 
     2020,6(1)-5-12. 
26. Zhan  S, Fan G, Cai M, Kou Z, Xu J, Cao Y, Bai L, Zhang Y, Jiang Y, Luo X, Xu J, Xu X, 
    Zheng L, Yu Z, Yang H, Zhang Z, Wang S, Tomberlin J*, Zhang J* and Huang Y*. Genomic 
    landscape  and  genetic  manipulation  of  the  black  soldier  fly  Hermetia  illucens,  a  natural 
    waste recycler. Cell Research, 2020, 30(1):50-60. 
27. Abdul  Aziz    Somroo,  Kashif  ur  Rehman,  Longyu       Zheng,  Minmin     Cai,  Xiaopeng  Xiao, 
    Shencai   Hu,   Alexander    Mathy,   Moritz   Gold,   Ziniu   Yu,  Jibin  Zhang*.    Influence   of 
    Lactobacillus buchneri  on  soybean  curd residue co-conversion by black  soldier  fly  larvae 
    (Hermetia    illucens)  for  food   and   feedstock   production.    Waste   Management,      2019, 
    86:114-122. 
28. Kashif ur Rehman, Rashid Ur Rehman, Abdul Aziz  Somroo, Minmin Cai, Longyu Zheng, 
    Xiaopeng  Xiao, Asif  Ur  Rehman, Abdul  Rehman,  Jeffery  K. Tomberlin,  Ziniu  Yu,  Jibin 
    Zhang*.    Enhanced    bioconversion    of dairy  and   chicken   manure   by   the  interaction  of 
    exogenous  bacteria  and  black  soldier  fly  larvae.  Journal  of  Environmental  Management, 
    2019, 237: 75-83. 
29. Yile  Zhai,  Zongze  Shao,  Minmin  Cai,  Longyu  Zheng,  Guangyu  Li,  Ziniu  Yu  and  Jibin 
    Zhang*.    Cyclo(L-Pro–L-Leu)      of Pseudomonas      p utida  MCCC     1A00316     isolated  from 
    Antarctic soil: identification and characterization of activity against Meloidogy ne incognita. 
    Molecules 2019, 24(768):1-15. 
30. Minmin Cai, Ke Zhang, Weida Zhong, Nian Liu, Xiangj i Wu, Wu Li, Longyu Zheng, Ziniu 
     Yu,  Jibin  Zhang*.  Bioconversion-composting  of  golden  needle  mushroom  (Flammulina 
     velutip es) root waste by black soldier fly (Hermetia illucens, Diptera: Stratiomyidae) 
     larvae, to obtain added-value biomass and      fertilizer. Waste    and   Biomass    Valorization. 
     2019, 10:265-273. 
31. Cai, M., Ma,  S., Hu, R., Tomberlin, J. K., Thomashow, L.  S., Zheng, L., Li, W., Yu, Z., 
     Zhang,  J*.  Rapidly  mitigating  antibiotic  resistant  risks  in  chicken  manure  by  Hermetia 
     illucens  bioconversion    with  intestinal  microflora.  Environmental     Microbiology,    2018, 
     20(11):4051-4062. 
32. Cai Minmin, Ma Shiteng, Hu Ruiqi, Jeffery K. Tomberlin, Yu Chan, Huang Yongping, Zhan 
    Shuai,  Li  Wu,  Zheng  Longyu,  Yu  Ziniu,  Zhang  Jibin*.  Systematic  characterization  and 
    proposed pathway of tetracycline      degradation    in  solid   waste   treatment   by   Hermetia 
    illucens with intestinal     microbiota. Environmental Pollution, 2018, 242:634-642. 
33. Xiaopeng  Xiao,  Lorenzo  Mazza, Yongqiang Yu, Minmin  Cai, Longyu  Zheng,  Jeffery  K. 
    Tomberlin, Jeffrey Yu, Arnold van Huis, Ziniu Yu, Salvatore Fasulo, Jibin Zhang*. Efficient 
    co-conversion    process   of chicken   manure    into  protein  feed  and   organic  fertilizer by 
    Hermetia  illucens  L.  (Diptera:  Stratiomyidae)  larvae  and  functional  bacteria.  Journal  of 
    Environmental Management,2018, 2 17:668-676. 
 34. Dian Huang, Zong-Ze Shao, Yi Yu, Min-Min Cai, Long-Yu Zheng, Guang-Yu Li, Zi-Niu 
     Yu,  Xian-Feng  Yi,  Jibin  Zhang*,  and  Fu-Hua  Hao*.  Identification,  characteristics  and 
     mechanism     of  1-Deoxy-N-acetylglucosamine        from  deep-sea    Virgibacillus  dokdonensis 
     MCCC 1A00493. Marine Drugs, 2018, 16, 52:1-13. 
﻿ 35. Yile Zhai, Zongze  Shao, Minmin  Cai, Longyu  Zheng, Guangyu  Li, Dian  Huang, Wanli 
     Cheng,     Linda  S. Thomashow, David  M. Weller, Ziniu Yu  and  Jibin  Zhang*. Multiple 
     Modes of Nematode Control by Volatiles of Pseudomonas p utida 1A00316 from Antarctic 
     Soil against Meloidogy ne incognita. Frontier in Microbiology. 2018, 9:253. 
 36. Xiao XX, Jin P, Zheng LY, Cai MM, Yu ZN, Yu J and Zhang JB*. Effects of black soldier 
     fly  (Hermetia illucens) larvae meal protein  as a fishmeal replacement  on the growth  and 
     immune     index  of  yellow   catfish  (Pelteobagrus   f ulvidraco). Aquaculture    Research. 
     2018;49:1569-1577. 
 37. Minmin  Cai, Ruiqi Hu, Ke Zhang, Shiteng Ma, Longyu  Zheng, Ziniu Yu, Jibin Zhang*. 
     Resistance of black  soldier  fly  (Diptera: Stratiomyidae) larvae to combined heavy metals 
     and  potential  application  in  municipal  sewage  sludge  treatment.  Environmental  Science 
     and Pollution Research.2018, 25(2):1559-1567. 
 38.  Kashif  ur  Rehman,   Rehman,  A,    Cai  M,  Xiao   X,  Zheng   L, Zhang   Ke,  Abdul  Aziz 
     Soomro,Wang Hui, Liu Xiu, Li Wu, Yu Ziniu, Zhang, Jibin*. Conversion of               mixtures 
     of dairy  manure  and  soybean  curd residue by black  soldier  fly  larvae  (Hermetia  illucens 
     L.). Journal of Cleaner Production.2017, 154: 366-373. 
 39. Wanli  Cheng, Jingyan Yang,  Qiyu  Nie, Dian  Huang,  Chen Yu, Longyu  Zheng, Minmin 
     Cai, Linda  S. Thomashow, David M. Weller, Ziniu Yu  & Jibin  Zhang*. Volatile organic 
     compounds  from  Paenibacillus p oly myxa  KM2501-1 control Meloidogy ne  incognita  by 
     multiple strategies. Scientific Report, 2017, 7: 162 13. 
 40. Kashif ur Rehman, Minmin  Cai, Xiaopeng Xiao, Longyu Zheng, Hui Wang, Abdul Aziz 
     Soomro,Yusha Zhou, Wu Li, Ziniu Yu, Jibin Zhang*. Cellulose decomposition and larval 
     biomass   production   from  the  co-digestion  of  dairy  manure   and  chicken   manure   by 
     mini-livestock   (Hermetia   illucens L.).  Journal  of Environmental    Management,     2017, 
     196:458-465. 
 4 1. Elhag  O, Zhou  D,  Song  Q,  Soomro A A, Cai M, Zheng  L, Yu  Z, Zhang J*.  Screening, 
     expression,  purification  and  functional  characterization  of  novel antimicrobial  peptide 
     genes from Hermetia illucens (L.). PLoS One. 2017,12(1): e0169582. 
 42. Cao Yu, Cheng Wanli, Huang Dian, Zheng Longyu, Cai Minmin, Lin Da, Yu            Ziniu, Zhang 
     Jibin*.Preparation   and    characterization   of   Iturin   a   microcapsules    in   sodium 
     alginate/poly(γ-glutamic acid) by spray drying. Journal International   Journal  of  Polymeric 
     Materials and Polymeric Biomaterials. 2017, 66     （10 ）:479-484. 
 43. Guo Jing#, Jing Xueping#, Peng Wen-Lei#, Nie Qiyu#, Zhai Yile, Shao Zongze ,          Zheng 
     Longyu, Cai Minmin, Li Guangyu, Zuo Huaiyu, Zhang Zhitao, Wang Rui-Ru, Huang Dian, 
     Cheng  Wanli,  Yu  Ziniu,  Chen   Ling-Ling*  &  Zhang  Jibin*.  Comparative  genomic  and 
     functional analyses: unearthing the diversity and     specificity of  nematicidal   factors  in 
    Pseudomonas p utida strain 1A00316.      Scientific Reports. 2016. 6:292 11. 
44.  Wang   Xuefei   , Mavrodi   V.  Dima   , Ke  Linfeng,   Mavrodi   V.  Olga,  Yang  Mingming, 
    Thomashow S. Linda, Zheng Na, Weller M David.* and Zhang Jibin*. Biocontrol and plant 
    growth-promoting  activity  of  rhizobacteria  from  Chinese  fields  with  contaminated  soils. 
    Microbial Biotechnology. 2015, 8(3):404-4 18. 
45.  Zhou    Fen,  Jeffery   K.  Tomberlin,    Zheng   Longyu,    Yu   Ziniu,  and   Zhang    Jibin* 
     Developmental     and  waste   reduction   plasticity  of  three  black   soldier  fly  strains 
     (Diptera: Stratiomyidae) raised on different livestock manures. Journal of Medical 
     Entomology. 2013, 50: 1224-1230. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name       Min ZHANG               Gender                  male 

         Position Title                          Professor 
                                                                                     Photo 
     Working Department           College of Life Sciences & Technology 

    Email                      minzhang@mail.hzau.edu.cn 

  Address           No.1, Shizishan Rd., Wuhan 430070, P. R. China 

     Tel                                                 Fax 

Research Interest 

     the mechanism of hypoxia 

Molecular mechanism of cancer and related clinical research 

Professional Memberships 

Other Roles 

 Education & Working Experience 

     2015-present, professor,  College  of  Life  Sciences  &  Technology,  Huazhong Agricultural 
     University, Wuhan, China. 
     2009-2015, Postdoc, School of Veterinary Medicine, University of California, Davis 
     2008-2009, Assistant  fellowship, Protein  Engineering, Institute of Hydrobiology, Chinese 
     Academy of Sciences，Wuhan, China. 
     2003-2008, Ph. D, hydrobiology, Institute of Hydrobiology, Chinese Academy of Sciences, 
     Wuhan, China. 
      1998-2002,   B.A.  College  of  Fisheries, College   of  Fisheries, Huazhong    Agricultural 
     University, Wuhan, China. 

 Publications 
﻿1.Zhang, M., Xu, E., Zhang, J. & Chen, X. PPM 1D phosphatase, a target  of p53 and RBM38 

RNA-binding    protein, inhibits p53 mRNA     translation via dephosphorylation  of RBM38. 

Oncogene 34, 5900-5911, doi:10.1038/onc.2015.31 (2015). 

2.Zhang, M., Zhang, J., Chen, XL., Cho,  SJ., Chen, XB. (2013)  Glycogen  synthase kinase  3 

promotes p53 mRNA translation via phosphorylation of RNPC 1. Genes & Development 27(20): 

2246-2258. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name      Shixue ZHENG             Gender                  Man 

         Position Title                          Professor 

     Working Department 

    Email                       zhengsx@mail.hzau.edu.cn 

  Address 

     Tel                 86-27-87294 148                 Fax 

Research Interest 

     My research focus on environmental microbiology: 

1.      Molecular  mechanisms  of heavy  metals  & metalloids transformation, in particularly,  on 

    selenium transformation in microorganisms & plants. 

2.   Bioremediation of heavy metals & metalloids. 

3.   Interactions between microorganisms & plants. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

      2013 - 2014: University of Copenhagen, Denmark, Postdoc in Microbiology. 

      1999 - 2007: Huazhong Agricultural University (HZAU), PhD in Microbiology. 
﻿     1992 - 1995: Central China Normal University, Master in Botany. 

     1988 - 1992: Shaanxi Normal University, Bachelor in Biology. 

Professional Experiences: 

     2019 - present: Professor, State Key Laboratory of Agricultural Microbiology, College of 

Life Science and Technology, HZAU, China 

     2004  -  2019:  Associate  professor,  State  Key  Laboratory  of  Agricultural  Microbiology, 

College of Life Science and Technology, HZAU, China 

     1997 - 2004: Lecturer, College of Life Science and Technology, HZAU, China 

     1995 - 1997: Teaching Assistant, College of Life Science and Technology, HZAU, China. 

Publications 

1.     Dan Wang, Xian Xia, Shijuan Wu, Shixue Zheng*, Gej iao Wang*. The essentialness of 

     glutathione  reductase  GorA   for  biosynthesis  of  Se(0)-nanoparticles  and  GSH   for CdSe 

     quantum  dot  formation  in  Pseudomonas  stutzeri  TS44.  Journal  of  Hazardous  Materials 

     (2019) 366: 301-310. https://doi.org/ 10.1016/j .j hazmat.2018.11.092 

2.    Shijuan Wu, Tengfei Li, Xian Xia, Zij ie Zhou, Shixue Zheng*, Gej iao Wang*. Reduction 

     of tellurite in  Shinella sp. WSJ-2  and adsorption removal of multiple dyes and metals by 

     biogenic tellurium nanorods. International Biodeterioration & Biodegradation  (2019)  144: 

     104751. 

3.      Dahui  Zhu,  Yaxin  Niu, Dongmei  Liu,  Gej iao  Wang,  Shixue  Zheng*.  Sphingomonas 

     gilva sp.  nov.,  isolated  from  mountain  soil.  Int  J Syst  Evol  Microbiol.  (2019)  69(11): 

     3472-3477. doi: 10.1099/ij sem.0.003645 

4.     Yuanqing Tan, Yuantao Wang, Yu Wang, Ding Xu, Yeting Huang, Dan Wang, Gej iao 

     Wang,  Christopher  Rensing,  Shixue Zheng*. Novel  mechanisms  of  selenate  and  selenite 

     reduction  in the  obligate  aerobic  bacterium   Comamonas      testosteroni S44.  Journal   of 

     Hazardous Materials (2018) 359: 129-138. 
﻿5.     Ding Xu, Lichen Yang, Yu Wang, Gej iao Wang, Christopher Rensing, Shixue Zheng*. 

     Proteins  enriched  in  charged   amino   acids  control  the  formation   and  stabilization  of 

     selenium nanoparticles in Comamonas testosteroni S44. Scientific Reports (2018) 8: 4766. 

     DOI:10.1038/s4 1598-018-23295-5. 

6.    X. Xia, S. Wu, N. Li, D. Wang, S. Zheng, G. Wang*. Novel bacterial selenite reductase 

     CsrF   responsible    for  Se(IV)   and    Cr(VI)   reduction   that   produces    nanoparticles 

     in  Alishewanella     sp.  WH 16-1.     J.  Hazard    Mater    (2018)   342:   499-509.    DOI: 

     http ://dx.doi.org/  10.1016/j .j hazmat.2017.08.051 

7.     Y. Wang, D. Xu, A. Luo, G. Wang, S. Zheng*. Nocardioides litorisoli sp. nov., isolated 

     from lakeside soil. Int J Syst Evol Microbiol (2017) 67: 42 16-4220. 

8.          Zhiyong   Wang,    Yuanqing    Tan,  Ding   Xu,  Gej iao  Wang,   Jihong   Yuan,   Shixue 

     Zheng*. Pedobacter vanadiisoli sp. nov., isolated from soil of a vanadium mine. Int J Syst 

     Evol Microbiol (2016) 66: 5112-5117. doi: 10.1099/ij sem.0.001480 (2016). 

9.                 Yuanqing     Tan,   Yuantao    Wang,     Dan   Wang,     Gej iao  Wang,     Shixue 

     Zheng*. Sphingoaurantiacus capsulatus sp. nov., isolated from mountain soil, and emended 

     description  of  the  genus   Sphingoaurantiacus.    Int J  Syst  Evol   Microbiol   (2016)  66: 

     4930-4935. doi: 10.1099/ij sem.0.001447 (2016). 

10.  Yuanqing Tan, Rong Yao, Rui Wang, Dan Wang, Gej iao Wang, Shixue Zheng*. Reduction 

     of selenite to Se(0) nanoparticles by filamentous bacterium Streptomyces sp. ES2-5 isolated 

     from   a   selenium   mining    soil.  Microbial    Cell  Factories   (2016)    15:  157.   DOI 

     10.1186/s12934-016-0554-z 

11.  Ding Xu, Libing Wang, Gej iao Wang, Shixue Zheng*. Domibacillus antri sp. nov., isolated 

     from   the  soil of  a  cave.   Int J  Syst   Evol  Microbiol    (2016)   66:  2502-2508.    doi: 

     10.1099/ij sem.0.001080. 

12.  Haichuan Cao, Ruirui Chen, Libing Wang, Lanlan Jiang, Fen Yang, Shixue Zheng*, Gej iao 

     Wang, Xiangui Lin. Soil pH, total phosphorus, climate and distance are the maj or  factors 

     influencing microbial  activity  at  a regional  spatial  scale.  Sci. Rep. (2016)  6: 25815. doi: 
﻿     10.1038/srep25815. 

13.   Shixue Zheng, Haichuan  Cao,  Qiaoyun  Huang, Ming  Liu, Xiangui  Lin, Zhongpei  Li*. 

    Long-term    fertilization  of  P  coupled  with  N greatly  improved  microbial  activities  in  a 

    paddy soil ecosystem derived from infertile land. European Journal of Soil Biology (2016) 

    72: 14-20. DOI: 10.1016/j .ej sobi.2015.12.006 

14.      Leilei  Zhang,   Shuij iao  Liao,  Yuanqing    Tan,   Gej iao  Wang,   Dan    Wang,   Shixue 

    Zheng*.  Chitinophaga  barathri     sp.  nov.,  isolated from   mountain   soil.  Int J Syst  Evol 

    Microbiol (2015) 65: 4233-4238. DOI 10.1099/ij sem.0.000566. 

15.   Guiqin  Song,  Ruirui  Chenb,  Wanwan  Xiang,  Fen  Yang,  Shixue  Zheng*,  Jibin  Zhang, 

    Jiabao   Zhang,    Xiangui   Lin*.   Contrasting   effects  of  long-term    fertilization on   the 

    community  of  saprotrophic  fungi  and  arbuscular  mycorrhizal  fungi  in  a  sandy  loam  soil. 

    Plant Soil Environ. (2015) 61(3): 127-136 

16.  S. Zheng, J. Su, L. Wang, R. Yao, D. Wang, Y. Deng, R. Wang, G. Wang*, C. Rensing*. 

     Selenite reduction by the obligate aerobic bacterium Comamonas testosteroni S44 isolated 

    from    a   metal-contaminated     soil.  BMC     Microbiology     (2014)    14:   204-2 16.   doi: 

     10.1186/s12866-014-0204-8. 

17.    W.  Xiang,    G.  Wang,  Y.  Wang,  R.  Yao,  F.  Zhang,  R.  Wang,  D.  Wang,        S.  Zheng 

     *.  Paenibacillus selenii  sp.  nov.,  isolated  from selenium  mineral   soil.  Int J Syst  Evol 

    Microbiol (2014) 64: 2662-2667. doi: 10.1099/ij s.0.063701-0 

18.  Shixue Zheng, Junli Hu, Xuefei Jiang, Fengqin Ji, Jiabao Zhang, Ziniu Yu*, Xiangui Lin*. 

    Long-term  fertilization regimes influence FAME profiles of microbial  communities in  an 

    arable  sandy  loam   soil  in  Northern  China.  Pedobiologia  -  Int.  J.  Soil  Biol.  (2013)  56: 

     179-183. 

19.   S. Zheng, J. Hu, K. Chen, J. Yao, Z. Yu*, X. Lin*. Soil microbial activity measured by 

    microcalorimetry in response to long-term fertilization regimes and available phosphorous 

    on heat evolution. Soil Biology & Biochemistry (2009) 4 1: 2094-2099. 
﻿                            CURRICULUM VITAE 

Personal Information 

    Name      Zhipeng ZHOU             Gender                  Man 

         Position Title                           Professor 

     Working Department 

    Email                     zhouzhipeng@mail.hzau.edu.cn 

  Address 

                                                                                      Photo 
     Tel                  027-87284305                    Fax 

Research Interest 

1.  Translational regulation; 

2.  The molecular mechanisms of circadian clock; 

3.  The biological functions of mRNA, tRNA, and rRNA modifications. 

Professional Memberships 

Other Roles 

 Education & Working Experience 

 Education: 

           09/2007 – 06/2012 Ph.D. Advisor: Dr. Qun He 

           College of Biological Sciences, China Agricultural University (CAU), Beij ing, China. 

           09/2003 – 06/2007 B.S. 

           College of Biological Sciences, China Agricultural University (CAU), Beij ing, China. 
﻿Professional Experiences: 

          09/2013– present, Professor, 

          College of Life Science and Technology, Huazhong Agricultural University, China. 

          06/2013– 09/2018, Postdoctoral Research associate with Dr. Yi Liu, 

          Department of Physiology, UT Southwestern Medical Center, Dallas, USA. 

          06/2012– 06/2013, Postdoctoral Research associate with Dr. Zhiyong Liu, 

          College of Agriculture and Biotechnology, CAU, Beij ing, China. 

Publications 

1.     Zhou, Z.*, Dang, Y.*#, Zhou, M., Yuan, H., and Liu, Y#. (2018). Codon usage biases 

     co-evolve with the transcription termination machinery to suppress premature cleavage and 

     polyadenylation in coding regions. eLife 7: 33569 (*Contributed equally) 

2.    Dang, Y. *, Cheng, J. *, Sun, X., Zhou, Z., and Liu, Y#. (2016). Antisense transcription 

     licenses  nascent   transcripts  to   mediate   transcriptional   gene   silencing.  Genes    & 

     Development, 30 (2 1), 24 17-2432. 

3.    Zhou, Z.*, Dang, Y.*, Zhou, M., Li, L., Yu, C.H., Fu, J., Chen, S., and Liu, Y#. (2016). 

     Codon  usage  is  an  important  determinant  of  gene  expression  levels  largely  through  its 

     effects on  transcription.  Proc  Natl  Acad   Sci  USA    113,  E6117-E6125.    (*Contributed 

     equally) 

4.     Yu, C.H.*, Dang, Y.*, Zhou, Z.*, Wu, C., Zhao, F., Sachs, M.S., and Liu, Y#. (2015). 

     Codon    Usage   Influences   the   Local   Rate   of  Translation   Elongation   to   Regulate 

     Co-translational Protein  Folding. Mol  Cell  59, 744-754. (*Contributed  equally  and cover 

     story 

5.    Sun, G.*, Zhou, Z.*, Liu, X.*, Gai, K., Liu, Q., Cha, J., Kaleri, F.N., Wang, Y., and He, 

     Q#.  (2016).  Suppression   of  WHITE    COLLAR-independent       frequency   Transcription  by 

     Histone   H3   Lysine   36  Methyltransferase    SET-2   Is  Necessary    for  Clock   Function 

     in Neurospora. J Biol Chem 291, 11055-11063. (*Contributed equally) 
﻿6.   Zhou, Z.*, Liu, X.*, Hu, Q.*, Zhang, N., Sun, G., Cha, J., Wang, Y., Liu, Y., and He, Q#. 

    (2013).  Suppression  of  WC-independent    frequency  transcription  by  RCO-1  is  essential 

    for Neurospora circadian clock. Proc Natl Acad Sci USA  110, E4867-4874. (*Contributed 

    equally) 

7.   Zhou, Z., Wang, Y., Cai, G., and He, Q#. (2012). Neurospora COP9 signalosome integrity 

    plays maj or roles for hyphal growth, conidial development, and circadian  function. PLoS 

    Genet 8, e1002712. 

8.   Wang, J., Hu, Q., Chen, H., Zhou, Z., Li, W., Wang, Y., Li, S., and He, Q#. (2010). Role of 

    individual subunits of the Neurospora crassa CSN complex in regulation of deneddylation 

    and stability of cullin proteins. PLoS Genet 6, e1001232. 
 
"""

def clean_multiline_text(text: str) -> str:
    """
    Cleans a captured multi-line text block by removing extra whitespace
    and joining lines with a single space.
    """
    lines = [line.strip() for line in text.strip().split('\n')]
    non_empty_lines = [line for line in lines if line]
    cleaned_text = ' '.join(non_empty_lines)
    return re.sub(r'\s+', ' ', cleaned_text).strip()

def extract_professor_info(text: str) -> list:
    """
    Extracts name, email, and research interest from each CV in the text.
    """
    professors = []
    profiles = text.split('CURRICULUM VITAE')[1:]

    for profile in profiles:
        name_match = re.search(r'Name\s+(.*?)\s+Gender', profile, re.DOTALL)
        name = clean_multiline_text(name_match.group(1)) if name_match else 'Not Found'

        email_match = re.search(r'Email\s+([\w.-]+@[\w.-]+)', profile)
        email = email_match.group(1).strip() if email_match else 'Not Found'

        interest_match = re.search(
            r'Research Interest\s+(.*?)\s+(?:Professional Memberships|Other Roles|Education & Working Experience|Publications)',
            profile,
            re.DOTALL
        )
        research_interest = clean_multiline_text(interest_match.group(1)) if interest_match else 'Not Found'

        if name != 'Not Found':
            professors.append({
                'name': name,
                'email': email,
                'research_interest': research_interest
            })
    return professors

# Extract the data
professor_data = extract_professor_info(text_content)
output_filename = 'professor_info.txt'

# Write the extracted information to a text file
try:
    with open(output_filename, 'w', encoding='utf-8') as f:
        if professor_data:
            for i, prof in enumerate(professor_data):
                f.write(f"Name: {prof['name']}\n")
                f.write(f"Email: {prof['email']}\n")
                f.write(f"Research Interest: {prof['research_interest']}\n")
                # Write a separator between entries, but not after the last one
                if i < len(professor_data) - 1:
                    f.write("---\n")
            print(f"Successfully saved professor information to '{output_filename}'")
        else:
            f.write("No professor information could be extracted.\n")
            print("No professor information was found to save.")
except IOError as e:
    print(f"Error writing to file: {e}")