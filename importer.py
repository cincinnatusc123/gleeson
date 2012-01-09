from collimator import Collimator, Source
from variant import Variant
import globes
from seattle import SeattleSource
import db
from math import log
import broad
from plates import Pilot, PlateI, PlateII, PlateIII, CIDR, Frazer_ali2, Frazer_aligned, FrazerII, PlateIV, PlateIV_1, PlateIV_2, PlateIV_3, PlateV_1, PlateV_2, PlateV_3, PlateV_4

##########  CONFIGURE ########################################
# dry_run = True means everything expect the execution of any database update
# queries get run.  The queries that would have been run are printed instead
# Good for ensuring no errors get thrown half way through inserting and for 
# checking that the insert queries make sense (columns are lining up, etc)
dry_run = False 

#Can specify what data is to be inserted.  It is a list of (plate,switch) 
#tuples.  Modify plates.py to add a new plate object.
plates_and_switches = [(PlateV_1(),'indel')]

#Run with python importer.py

############ /CONFIGURE  ####################################3

############# GLOBALS ########################################

conn = db.Conn("localhost",dry_run=dry_run)

# X_cols are the columns of the database table we want to fill
# X_cols_tograb is the data we can fetch directly from the Variant object
# the other columns are things like primary and foreign keys that link 
# the rows together
variant_cols = conn.getColumns("Variants")
call_cols = conn.getColumns("Calls")
call_cols_tograb = call_cols[3:]
iso_cols = conn.getColumns("Isoforms")
iso_cols_tograb = iso_cols[2:]

#make patient name->id lookup
results = conn.query( "select id,name from Patients" )
patients_dbix = {}
for (ID,name) in results :
    patients_dbix[name] = int(ID)

############## /Globals  ###########################################


def insertPlate( conn, plate, switch ) :
    inserted_count = 0
    updated_count = 0
    iso_count = 0
    hold1 = 0
    hold2 = 0
    iso = 0
    #We will keep track which plate each call comes from.
    plate_id = plate.getPlateID()

    # Construct the Sources for a Collimator to work on
    ff = 0
    vcfSource = broad.VCFSource( plate.varFile(switch), fast_forward = ff )
    ff = 1
    seattleSource = SeattleSource( plate.seattleFile(switch), switch, fast_forward = ff )
    sources = [vcfSource, seattleSource]

    populatePatients( conn, vcfSource.patients )
    c = Collimator( sources, comparator, targetCreator )
    for i,var in enumerate(c) :
        if i % 5000 == 0 : print "%d variants processed" % i
        iso_count = iso_count + hold1
        iso = iso + hold2
        values = var.getPosition()
        vid = getVariantID( values )
        #vid = False
        if not vid :
            inserted_count += 1
            hold1,hold2 = insertVariant( conn, var, plate_id,0,0 )
        else :
            updated_count += 1
            addToCalls( conn, vid, var, plate_id )
    
    print "Plate: %d" % plate_id
    print "    inserted", inserted_count
    print "    updated", updated_count
    print "    Isoforms", iso_count
    print "    All Iso" , iso
#method needed to construct a Collimator
def comparator(a,b) :
    return globes.compareVariants( a[0],a[1],a[2],a[3],b[0],b[1],b[2],b[3] )

#method needed to construct a Collimator
def targetCreator() :
    return Variant([],[])

#Would very much like to speed up this process, dont see how
def getVariantID( var_tuple ) :
    query = '''select id
               from Variants as v
               where v.chrom = %s
                 and v.pos = %s
                 and v.ref = '%s'
                 and v.mut = '%s' ''' \
            % (var_tuple[0],var_tuple[1],var_tuple[2],var_tuple[3])

    return conn.queryScalar( query, int )

#deprecated.....
def variantToDatabase( conn, variant ) :
    global inserted_count, updated_count
    keys = ["chrom","pos","ref","mut"]
    values = [variant.fields[k] for k in keys]
    #print "adsfasfasfdasdfasdfasdf"
    #print values
    vid = getVariantID( values )
    if not vid :
        inserted_count += 1
        insertVariant( conn, variant )
    else :
        updated_count += 1
        addToCalls( conn, vid, variant )

#We have a brand new variant, put it into the db
def insertVariant(conn, variant, plate_id, count,isoforms) :
    variant_dbix = conn.getNextID("Variants")
    values = variant.getFields( variant_cols )
    #pos = variant.getPosition()[1]
    values[0] = variant_dbix

    if switch == 'indel': tipe = 2
    else : tipe = 1
    typeix = variant_cols.index("type")
    values[typeix] = tipe

    #insert the variants
    conn.insert( 'Variants', values, variant_cols )
    prevIso = -1
    #insert the isoforms
    for iso in variant.isoforms :
        isoforms = isoforms +1;
        isoCur = iso.getFields( iso_cols_tograb )
        if( isoCur != prevIso):
            prevIso = isoCur
            iso.fields['gene_id'] = geneIDFromName( conn, iso.fields["gene"] )
            #print iso
            values = [variant_dbix] + iso.getFields( iso_cols_tograb )
            conn.insert( "Isoforms", values, iso_cols[1:] )
            count = count +1
        else: 
            prevIso = isoCur

    #insert the calls
    for call in variant.base_calls :
        pat_dbix = patients_dbix[call.pat_name]
        values = [variant_dbix, pat_dbix, plate_id] + \
                 call.getFields( call_cols_tograb )
        conn.insert( 'Calls', values, call_cols) #, skip_dupes=True )
    return count, isoforms
# This variant (identified by vid) has already been added to the system
# By definition so have the isoforms
# The calls, however, are novel
def addToCalls(conn, vid, variant, plate_id) :
    #Do we want to integrate quality score here?  Doing a weighted average
    #by the number of calls?
    for call in variant.base_calls :
        #pat_dbix = lookupPatientID( call )
        pat_dbix = patients_dbix[call.pat_name]
        values = [vid, pat_dbix, plate_id] + \
                 call.getFields( call_cols_tograb )
        conn.insert( 'Calls', values, call_cols, skip_dupes=True )

#Add the patient names to the Patients table
@db.catch
def populatePatients( conn, patient_names ) :
    patient_dbix = conn.getNextID("Patients");
    for patient in patient_names :
        query = "select id from Patients where name='%s'" % patient
        pid = conn.queryScalar(query,int)
        if not pid :
            patient = broad.sanitizePatientName( patient )
            conn.insert( "Patients", [patient_dbix,patient], ["id","name"] )
            patients_dbix[patient] = patient_dbix

        patient_dbix += 1

#Given a BaseCall object (see variant.py), get the actual patient name
def lookupPatientID( call ) :
    patient_name = vcfSource.patients[call.pat_ix]
    return patients_dbix[patient_name]

def geneIDFromName( conn, gene_name ) :
    query = "select id from Genes where geneSymbol = '%s'" % gene_name
    gene_ids = conn.query( query )
    if not gene_ids :
        gid = -1 #makeEmptyGene( conn, 'refseq', accession )
    elif len(gene_ids) == 1 :
        gid = int(gene_ids[0][0])
    else :
        #'what to do when an accession: %s matches multiple Genes %s?' % (accession, str(gene_ids))
        #take the first one
        gid = int(gene_ids[0][0])

    return gid

if __name__ == '__main__' :
    for plate,switch in plates_and_switches :
        insertPlate( conn, plate, switch )


###############################################################################
###############################################################################
#unfinished.  Idea was to remove Calls that were spurious,
#then removed the Variants, Patients, and Isoforms that got orphaned
def removeCalls() :
    plate_id = plates.ids("PlateV_2")

    #delete all Calls that are old
    query = '''
delete Calls
where plate = %d''' % plate_id

    #delete any stranded variants
    query = '''
    delete v
    from Variants as v left join Calls as c on v.id = c.var_id
    where c.var_id is null
    '''

    query = '''
    delete i
    from Isoforms as i left join Variants as v on v.id = i.var_id
    where v.id is null'''

    #delete any stranded patients
    query = '''delete p 
    FROM Patients AS p
    LEFT JOIN (

        SELECT DISTINCT pat_id
        FROM Calls
    ) AS t ON t.pat_id = p.id
    WHERE pat_id IS NULL
    '''


#############################################################################
            #OLd stuff
#############################################################################

#Hold over from when we were maintaining a Genes table.  Not used currently
@db.catch
def makeEmptyGene(conn,col,value) :
    nid = conn.getNextID("Genes")
    conn.insert( "Genes", [nid,value], ["id",col] )
    return nid


#quick hack to add in some missing variants
def insertMissingVariants(conn) :
    query = '''
   SELECT id,chrom,pos,ref,mut
   FROM (

       SELECT var_id
       FROM Calls AS c
       INNER JOIN Variants AS v ON c.var_id = v.id
       WHERE c.plate = 3
       AND TYPE =1
       GROUP BY var_id
   ) AS t inner join Variants as v on t.var_id = v.id
   ORDER BY chrom,pos,ref,mut
   '''

    rows = conn.query( query )
    print len(rows)
    it = iter(rows)
    def eqkey( it ) :
        return [int(it[1]), int(it[2]), it[3], it[4]]

    def integrator( target, it ) :
        return target

    def absentHandler( ae ) :
        print str(ae)
        if ae.ix == 2 :
            variantToDatabase( conn, ae.missed_target )
        else :
            assert False

    dbSource = Source( it, eqkey, integrator, allow_absent = False )

    c = Collimator( [vcfSource,seattleSource,dbSource], comparator, targetCreator, absentHandler = absentHandler )
    for i,v in enumerate(c) :
        if i % 5000 == 0 : print i
        pass #waiting for dbSource to be absent, this will trigger absentHandler

#quick hack to fix fill in the ref_aa/mut_aa columns
def seattleToDatabase( conn, seattleSource ) :
    count = 0
    for out_splt in seattleSource.iterate(fast_forward=0) :
        if count % 1000 == 0 : print "%d updated" % count
        count += 1
        vid = getVariantID( seattleSource.getPosition( out_splt ) )
        if vid :
            aas = out_splt[11].split(',')
            if len(aas) == 2 :
                conn.update('Variants',aas,['ref_aa','mut_aa'], vid)
        else :
            print "Seattle Row: %s has no matching variant in the Variants table" % str(out_splt)
            assert False

