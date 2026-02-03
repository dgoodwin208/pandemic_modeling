# White Paper Plan 

Be the expert modeler and validation-driven scientist who accepts that we have to build incrementally,but we have to build on a solid foundation. 

* 001 shows us that we can simulate invidual people and get SEIR-D curves out. 
* 002  shows us the right way to model the individual (rules based? Random based?) What did we chooose in the end?
* 003 shows us that we can model health care providers in the DES model and get reasonable results out. 
* 004 shows us that we can in principle model cities by ODEs (but we concluded that we're better off keeping it all as DES because DES is very fast) and that we get reasonable looking cross-city distribution
* 005 shows that we can do all cities in one country and that the numbers for the first ~100 days of covid-like can match the numbers in Nigeria (3000 total for whole pandemic, so just 1-2k range if deaths is good if our simuilation puts that out. Be sure to scale up our sampling of just the cities of nigeria to the whole population of nigeria)
* 006 shows that we can do the whole continent at numbers we believe are reasonable. We want to show that we can recapitulate the first wave of deaths in covid19 for the whole of Africa (65, 602 according to https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(21)00632-2/fulltext, and keep in mind that our cities are only a fraction of the total population of Africa). What parameters woudl we update to our model to get a reasonable death rate for the first wave?
* 007 explores the idea of how many healthcare workers are needed? This is where we explore a dose-dependent response on the healthcare workers for the overall outcome. We could use an ebola attack if we want to show a bigger delta
* 008 is the hardest of all, we can validate that once we're bulletrpoof on all the others

For each one of these subpieces, I want you to be both an expert software engineer who considers code reuse, modularity and interpretability AND I need you to also be a rigorous epidemiologist who is running validations, positive controls and negative controls constantly to be sure that you believe the simulation. 

Keep each step, as much as possible, modular within the 001/ 002/ ... folders. Write a white_paper_section_{description of step}.md in each folder containing the figures made by the code, a caption for each figure, and an academic style writeup explaining an introduction, methods, results. In the method section you can call out specific lines for code. 